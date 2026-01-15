from PharmaPy.Reactors import BatchReactor, CSTR, PlugFlowReactor, SemibatchReactor
from PharmaPy.Evaporators import Evaporator
from PharmaPy.SolidLiquidSep import Filter
from PharmaPy.Crystallizers import BatchCryst, MSMPR
from PharmaPy.Containers import Mixer, DynamicCollector
from PharmaPy.Phases import LiquidPhase, SolidPhase
from PharmaPy.Streams import LiquidStream, BatchToFlowConnector

from PharmaPy.ProcessControl import DynamicInput
from PharmaPy.Interpolation import PiecewiseLagrange

from PharmaPy.Utilities import CoolingWater


from helper import get_cryst_kinetics, get_cryst_kwargs, get_rxn_kinetics, get_rxn_kwargs

import numpy as np


def add_reactor(path=None, reactor_name=None, reactor_type=None,
                inputs=None, reactor_attributes=None,
                first_unit=False, first_batch=False,
                sim_obj=None, runargs=None):
    """
    Function to add a reactor to the simulation object. This function
    can add a batch, semibatch, CSTR, or PFR reactor to the flowsheet.
    This function is almost general, but is still tailored for the
    lomustine example for AIChE 2022, superstructure work.

    :param path: filepath, path to physical properties data
    :param reactor_name: string, name of the reactor for the flowsheet
    :param reactor_type: string, descriptor of the reactor in {'batch',
    'Semibatch', 'CSTR', 'PFR'}
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param reactor_attributes: dict, dictionary of extra attributes needed
    to add to the reactor object.
    :param first_unit: bool, default:False, if the unit is first, extra
    information is required (i.e., an inlet [continuous] or holdup [batch])
    :param first_batch: bool, default:False, boolean variable for whether
    the first unit was batch or not. Helps in determining the upstream
    flow of the previous units.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    # All units need kinetics and keyword arguments to
    # set up and run the unit
    kin = get_rxn_kinetics(path)
    kwargs = get_rxn_kwargs(reactor_type=reactor_type)
    reactor_runargs = {}

    # Logic for batch reactors. If first reactor, include phase.
    if reactor_type == 'batch':
        reactor = BatchReactor(**kwargs)

        if first_unit:
            conc_AB = inputs['c_in']
            conc_init = [conc_AB] * 2 + [0.0] * 7
            phase_R01 = LiquidPhase(path, vol=inputs['vol'], mole_conc=conc_init,
                                    temp=323.15, name_solv='THF')
            reactor.Phases = phase_R01

            # Also must add batch time to the run arguments
            reactor_runargs['runtime'] = inputs['time_R01']
        else:
            reactor_runargs['runtime'] = inputs['time_R02']

    # Logic for Semibatch reactors. (Always the ONLY reactor)
    elif reactor_type == 'Semibatch':
        reactor = SemibatchReactor(**kwargs)

        reactor_runargs['runtime'] = inputs['time_R01']

        conc_AB = inputs['c_in']
        conc_init = [conc_AB] * 2 + [0.0] * 7
        phase_R01 = LiquidPhase(path, vol=inputs['vol'], mole_conc=conc_init,
                                temp=323.15, name_solv='THF')

        conc_in = [0.0] * 3 + [10.0] + [0.0] * 5
        conc_in = np.array(conc_in)
        # Now define a new LiquidStream with no vol_flow argument
        dynamic_inlet = LiquidStream(path, temp=323.15,
                                     mole_conc=conc_in, name_solv='THF')

        # Define inlet_control as a dynamic output for dynamic flow
        inlet_control2 = DynamicInput()

        # Create a lagrange function that will make a linear
        # profile starting at 2*flowrate and ending at 0

        V_in = inputs['c_TBN'] * inputs['vol'] / (conc_in[3] - inputs['c_TBN'])
        flow_vals = np.array([V_in / (inputs['time_R01']) / inputs['time_feed'], 0.0],
                             dtype=np.float64)
        time_vals = [0.0, inputs['time_R01'] * inputs['time_feed'], inputs['time_R01']]
        lagrange = PiecewiseLagrange(inputs['time_R01'], y_vals=flow_vals,
                                     time_k=time_vals, order=1)

        # Add control to the inlet control for the 'vol_flow' variable
        inlet_control2.add_variable('vol_flow', lagrange.evaluate_poly)

        # Finally, set the LiquidStream's 'DynamicInlet' field to
        # the newly defined 'inlet_control' dynamic input
        dynamic_inlet.DynamicInlet = inlet_control2

        reactor.Phases = phase_R01
        reactor.Inlet = dynamic_inlet

    # Logic for continuous reactors. If first reactor, include the process inlet.
    else:
        if reactor_type == 'CSTR':
            reactor = CSTR(**kwargs)
        elif reactor_type == 'PFR':
            reactor = PlugFlowReactor(**kwargs)

        # Adding runtime for continuous unit. [10 hours]
        reactor_runargs['runtime'] = 10 * 3600
        if first_unit:
            conc_AB = inputs['c_in']
            conc_in = [conc_AB] * 2 + [0.0] * 7
            vol_flow = inputs['vol'] / inputs['tau_R01']
            inlet_R01 = LiquidStream(path, vol_flow=vol_flow, mole_conc=conc_in,
                                     name_solv='THF')
            reactor.Inlet = inlet_R01

            # Phase volume changes from first/second unit for continuous units.
            phase_vol = inputs['vol']
        else:
            # Upstream flow required to determine second reactor initial holdup.
            if first_batch:
                upstream_flow = inputs['vol'] / inputs['time_R01']
            else:
                upstream_flow = inputs['vol'] / inputs['tau_R01']
            phase_vol = upstream_flow * inputs['tau_R02']

        conc_init = [0.0] * 9
        phase_R01 = LiquidPhase(path, vol=phase_vol, mole_conc=conc_init,
                                temp=323.15, name_solv='THF')
        reactor.Phases = phase_R01

    # Finally, add kinetics and cooling water. (Identical for all unit types!)
    reactor.Kinetics = kin
    reactor.Utility = CoolingWater(temp_in=323.15, mass_flow=0.1)

    reactor_runargs['verbose'] = False
    reactor_runargs['sundials_opts'] = {'time_limit': 10.0, 'report_continuously': True}
    runargs[reactor_name] = reactor_runargs

    setattr(sim_obj, reactor_name, reactor)
    return sim_obj, runargs


def add_vaporizer(vaporizer_name=None, previous_batch=False, first_batch=False,
                  inputs=None, sim_obj=None, runargs=None):
    """
    Function to add a batch vaporizer to the flowsheet.

    :param vaporizer_name: string, name of the vaporizer
    :param previous_batch: bool, default:False, if the previous unit is batch,
    the phase is a phase. If not, the 'phase' is a stream.
    :param first_batch: bool, default:False, if the first reactor was batch,
    there is logic to determine the vol/vol_flow for MIX02.
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    vaporizer_runargs = {}
    # Need to calculate volume of the vaporizer drum
    vol_VAP01 = 0
    beta = 0.75  # Makes 25% of the volume space for vapor.
    factor = (1 + inputs['ratio_hept']) / beta
    if first_batch:
        if previous_batch:
            vol_VAP01 = inputs['vol'] * factor
        else:
            vol_VAP01 = inputs['vol'] / inputs['time_R01'] * 10 * 3600.0 * factor
    else:
        vol_VAP01 = inputs['vol'] / inputs['tau_R01'] * 10 * 3600.0 * factor

    # Writing the kw arguments
    kw_flash = {'seed_basedon_input': True}
    kw_VAP01 = {'pressure': inputs['pressure'], 'vol_drum': vol_VAP01,
                'flash_kwargs': kw_flash, 'include_nitrogen': False,
                'h_conv': 1000}
    vaporizer = Evaporator(**kw_VAP01)
    vaporizer.Utility = CoolingWater(temp_in=307.15, mass_flow=1.0)

    vaporizer_runargs['runtime'] = inputs['time_VAP01']

    vaporizer_runargs['verbose'] = False
    vaporizer_runargs['sundials_opts'] = {'time_limit': 10.0, 'report_continuously': True}
    # vaporizer_runargs['sundials_opts'] = {'time_limit': 30.0, 'report_continuously': True}
    runargs[vaporizer_name] = vaporizer_runargs

    setattr(sim_obj, vaporizer_name, vaporizer)
    return sim_obj, runargs


def add_crystallizer(path=None, cryst_name=None, cryst_type=None,
                     inputs=None, first_batch=False, all_batch=False,
                     sim_obj=None, runargs=None):
    """
    Function to add crystallizers to the flowsheet. Here, there is either
    a batch crystallizer (only unseeded currently) or a train of MSMPRs.
    The train is 1, 2, or 3 units long, and the logic creates this train
    with appropriate tank sizes to adjust residence times.

    :param path: filepath, path to physical properties data
    :param cryst_name: string, name of the unit
    :param cryst_type: string, type of crystallizers in {'batchS', 'batchU',
    'cont{n}'} where 'n' is in (1, 2, 3)
    :param first_batch: bool, default:False, if the first reactor was batch,
    there is logic to determine the vol/vol_flow for MIX02.
    :param all_batch: bool, default:False, if the whole flowsheet is batch
    before the crystallizers, there will be.
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """

    # ToDo: add options for continuous units? Depends on convergence issues
    kinetics = get_cryst_kinetics()
    cryst_kwargs = get_cryst_kwargs(cryst_type=cryst_type)

    cryst_runargs = {}

    # Creating the phases required for the Batch crystallizer
    x_dist = np.arange(1, 501)
    dist = np.zeros_like(x_dist)

    x_dist = np.geomspace(1, 500, 25)
    dist = np.zeros_like(x_dist)

    no_solid = SolidPhase(path, distrib=dist, x_distrib=x_dist,
                          mass_frac=[0] * 4 + [1, 0, 0, 0, 0])

    # ToDo: add logic for seeded crystallization? How does seeded crystallization work for a downstream unit?
    if 'batch' in cryst_type:
        # Creating temperature profile for Batch cooling crystallization
        temp_vals = [323.15, inputs['T_1'], inputs['T_2'], inputs['T_f']]

        temp_cry = np.array(temp_vals)

        temp_CR01 = np.zeros((len(temp_cry) - 1, 2))
        temp_CR01[:, 0] = temp_cry[:-1]
        temp_CR01[:, 1] = temp_cry[1:]

        interp_CR01 = PiecewiseLagrange(time_final=inputs['time_CR01'],
                                        y_vals=temp_CR01)

        control_CR01 = {'temp': interp_CR01.evaluate_poly}

        # Appending controls to the kwargs dictionary
        cryst_kwargs['controls'] = control_CR01

        # Adding the runtime
        cryst_runargs['runtime'] = inputs['time_CR01']

        # Making the unit
        cryst = BatchCryst(**cryst_kwargs)

        phases = no_solid

    else:
        # No extra kwargs required for
        cryst = MSMPR(**cryst_kwargs)

        # Must calculate the volume of the phases for chosen residence times.
        beta = 0.75
        factor = (1 + inputs['ratio_hept']) / beta
        cycle_time = 10.0 * 3600.0
        if first_batch:
            if all_batch:
                vol_VAP01 = inputs['vol'] * factor

                # Finding cycle time. Check if SB --> R02 doesn't exist!
                try:
                    time_R02 = inputs['time_R02']
                except:
                    time_R02 = 0.0
                max(inputs['time_R01'], time_R02, inputs['time_VAP01'])
            else:
                vol_VAP01 = inputs['vol'] / inputs['time_R01'] * 10 * 3600.0 * factor
        else:
            vol_VAP01 = inputs['vol'] / inputs['tau_R01'] * 10 * 3600.0 * factor

        effective_flow = vol_VAP01 / cycle_time  # m^3 / s
        vol_cryst = effective_flow * inputs['tau_' + cryst_name]  # initial phase volume in m^3

        liq_phase = LiquidPhase(path, mass_frac=[0]*8 + [1], vol=vol_cryst, temp=inputs['T_' + cryst_name])

        cooling = CoolingWater(temp_in=inputs['T_' + cryst_name], mass_flow=1.0)
        cryst.Utility = cooling

        cryst_runargs['runtime'] = 10 * 3600.0

        phases = (liq_phase, no_solid)

    cryst.Phases = phases
    cryst.Kinetics = kinetics

    if 'batch' in cryst_type:
        cryst_runargs['sundials_opts'] = {'maxh': 100.0, 'time_limit': 15.0, 'report_continuously': True}
    else:
        cryst_runargs['sundials_opts'] = {'time_limit': 15.0, 'report_continuously': True}
        # cryst_runargs['sundials_opts'] = {'time_limit': 35.0, 'report_continuously': True}
    cryst_runargs['verbose'] = False
    runargs[cryst_name] = cryst_runargs

    setattr(sim_obj, cryst_name, cryst)
    return sim_obj, runargs


def add_filter(filter_name=None, inputs=None,
               sim_obj=None, runargs=None):
    """
    Function to add a batch filter to the end of the flowsheet. All flowsheets
    will have the same filter, as the decision variables do not effect the
    objective function values.

    :param filter_name:
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    kwargs = {'station_diam': inputs['diam']}
    runargs_filter = {'deltaP': inputs['dP']}

    filter = Filter(**kwargs)

    runargs_filter['verbose'] = False
    runargs[filter_name] = runargs_filter

    setattr(sim_obj, filter_name, filter)
    return sim_obj, runargs


def add_mixer(path=None, mixer_name=None, previous_batch=False,
              first_batch=False, inputs=None,
              sim_obj=None, runargs=None):
    """
    Function to add a mixer to the simulation object. This function
    adds the appropriate flow or phase to be mixed depending on
    whether the previous unit operation was batch or not.

    :param path: filepath, path to physical properties data
    :param mixer_name: string, name of the mixer for the flowsheet
    :param previous_batch: bool, default:False, if the previous unit is batch,
    the phase is a phase. If not, the 'phase' is a stream.
    :param first_batch: bool, default:False, if the first reactor was batch,
    there is logic to determine the vol/vol_flow for MIX02.
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    # Unique logic for 1st or 2nd mixer
    if mixer_name == 'MIX01':
        mole_frac_TBN = [0.0] * 3 + [1.0] + [0.0] * 5
        if previous_batch:
            mole_TBN = inputs['c_TBN'] * inputs['vol'] * 1000  # mol
            phase_mix = LiquidPhase(path, moles=mole_TBN,
                                    mole_frac=mole_frac_TBN)
        else:
            vol_flow = inputs['vol'] / inputs['tau_R01']
            moleflow_TBN = inputs['c_TBN'] * vol_flow * 1000  # mol/s
            phase_mix = LiquidStream(path, mole_flow=moleflow_TBN,
                                     mole_frac=mole_frac_TBN)
    elif mixer_name == 'MIX02':
        mass_frac_hept = [0.0] * 8 + [1.0]
        if previous_batch:
            if first_batch:
                vol_hept = inputs['vol'] * inputs['ratio_hept']
                phase_mix = LiquidPhase(path, vol=vol_hept,
                                        mass_frac=mass_frac_hept)
            else:
                vol_hept = inputs['vol'] / inputs['tau_R01'] * 10 * 3600.0 * inputs['ratio_hept']
                phase_mix = LiquidPhase(path, vol=vol_hept,
                                        mass_frac=mass_frac_hept)
        else:
            if first_batch:
                flow_hept = inputs['vol'] / inputs['time_R01'] * inputs['ratio_hept']
                phase_mix = LiquidStream(path, vol_flow=flow_hept,
                                         mass_frac=mass_frac_hept)
            else:
                flow_hept = inputs['vol'] / inputs['tau_R01'] * inputs['ratio_hept']
                phase_mix = LiquidStream(path, vol_flow=flow_hept,
                                         mass_frac=mass_frac_hept)
    mixer = Mixer()
    mixer.Inlets = phase_mix



    # Only setting the mixer is required, no run arguments.
    setattr(sim_obj, mixer_name, mixer)
    return sim_obj, runargs


def add_hold(holder_name=None, sim_obj=None, runargs=None, curr_layout=None):
    """
    Function to add a holding tank to the flowsheet.

    :param holder_name: string, name of the holding tank
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    holder_runargs = {}
    holder_runargs['runtime'] = 10 * 3600.0

    holder = DynamicCollector()

    holder_runargs['verbose'] = False
    if 'cont' in curr_layout:
        holder_runargs['sundials_opts'] = {'time_limit': 15.0, 'report_continuously': True}
        # holder_runargs['sundials_opts'] = {'time_limit': 35.0, 'report_continuously': True}
    else:
        holder_runargs['sundials_opts'] = {'rtol': 1e-9, 'time_limit': 10.0, 'report_continuously': True}
        # holder_runargs['sundials_opts'] = {'rtol': 1e-9, 'time_limit': 30.0, 'report_continuously': True}
    runargs[holder_name] = holder_runargs

    setattr(sim_obj, holder_name, holder)
    return sim_obj, runargs


def add_b2f(b2f_name=None, curr_layout_unit=None, all_batch=False,
            inputs=None, sim_obj=None, runargs=None):
    """
    Function to add a batch-to-flow connector between an upstream
    batch unit to a continuous unit operation.

    :param b2f_name: string, name of the batch-to-flow connector
    :param curr_layout_unit: string, name of the current major piece
    of equipment. Used to determine if we are at the crystallizers or
    at the reactor train.
    :param all_batch: bool, default:False, flag for whether we must
    determine the batch to flow cycle time from batch times.
    :param inputs: dictionary, keys are operational variables with the value
    being the respective value for that key.
    :param sim_obj: SimulationExecutive object, PharmaPy simulation object
    that will be returned with the new reactor attached.
    :param runargs: dictionary, dictionary of run arguments for all the
    units in the flowsheet.

    :return: sim_obj, SimulationExecutive object, returns the sim_obj with
             the new unit operation attached.
             runargs, dictionary of dictionaries, updated with the runargs
             required for the unit added to the flowsheet.
    """
    cycle_time = 0
    if '1' in b2f_name:
        # If the first batch-to-flow connector is at the crystallizers,
        # then we determine the overall reactor train cycle time.
        if 'cont' in curr_layout_unit:
            if all_batch:
                # All batch means we need to find the cycle time
                # Test for semibatch. R02 doesn't exist!
                try:
                    time_R02 = inputs['time_R02']
                except:
                    time_R02 = 0.0

                cycle_time = max(inputs['time_R01'], time_R02, inputs['time_VAP01'])
            else:
                # Any continuous unit indicates we already ran to 10 hour sim at one point
                cycle_time = 10 * 3600.0
        else:
            # If we aren't at the crystallizers, we are between R01 and R02
            cycle_time = inputs['time_R01']
    else:
        # If we have a second batch-to-flow connector, we have case B-->C-->B-->C
        cycle_time = 10 * 3600.0

    b2f_conn = BatchToFlowConnector(cycle_time=cycle_time)

    # No run arguments for the batch-to-flow connector
    setattr(sim_obj, b2f_name, b2f_conn)
    return sim_obj, runargs
