import numpy as np
from PharmaPy.Kinetics import RxnKinetics, CrystKinetics
from PharmaPy.Commons import trapezoidal_rule


def solub_fn(temp, conc=None, mole_frac=None):
    """
    Parameters
    ----------
    temp : float or array-like
        temperature (between 255 and 305).
    conc : TYPE
        DESCRIPTION.
    Returns
    -------
    solub : TYPE
        DESCRIPTION.
    """
    mult_solub = 6.5

    mw = np.array([105.52, 99.1741, 204.6941, 103.1198, 233.7, 74.123, 179.643,
                   72.107, 100.205])

    if conc is not None:
        if conc.ndim == 1:
            w_frac = conc / conc.sum()

            x_frac = w_frac/mw / np.dot(w_frac, 1/mw)
            x_thf = x_frac[7]
        else:
            w_frac = conc / conc.sum(axis=1)[..., np.newaxis]

            x_frac = w_frac/mw / np.dot(w_frac, 1/mw)[..., np.newaxis]
            x_thf = x_frac[:, 7]

    elif mole_frac is not None:
        if mole_frac.ndim == 1:
            x_thf = mole_frac[7]
        else:
            x_thf = mole_frac[:, 7]

    a, b, c = np.array([3.24643349e+02, -2.53376972e+00,  4.97645771e-03])
    solub = a + b*temp + c*temp**2
    solub *= 1 + mult_solub * x_thf

    return solub


def get_rxn_kinetics(path):
    """
    Helper function to return reaction kinetics for a
    PharmaPy reactor object. Function applicable for
    the lomustine reaction system.

    :param path: file path for physical properties
    :return: RxnKinetics object
    """
    # Reaction
    rxns = ['ISO + CHA --> interm',
            'interm + TBN --> lom + TBA',
            'ISO + TBA --> SUB1']

    e_act = np.array([2e3, 2e3, 2e3])  # J/mol
    k_kin = np.array([210, 7, 4]) * 1e-2  # 1/s

    kin_rxn = dict(rxn_list=rxns, k_params=k_kin,
                   ea_params=e_act, delta_hrxn=[0]*3)

    kinetics = RxnKinetics(path, **kin_rxn)

    return kinetics


def get_cryst_kinetics():
    """
    Helper function to return reaction kinetics for a
    PharmaPy crystallizer object. Function applicable
    for the lomustine reaction system.

    :return: CrystKinetics object
    """
    prim = (3e8, 0, 3)  # kP in #/m3/s
    sec = (4.46e10, 0, 2, 1e-5)
    growth = (5, 0, 1.32)  # kG in m/s
    dissol = (1, 0, 1)

    solub_cts = np.array([2.269e2, -1.88e0, 3.89e-3])

    kin_cryst = dict(solub_fn=solub_fn, nucl_prim=prim, nucl_sec=sec,
                     growth=growth, dissolution=dissol)

    kinetics = CrystKinetics(**kin_cryst)

    return kinetics


def get_rxn_kwargs(reactor_type):
    """
    Helper function to return a dictionary that will
    be used to define a reactor in the lomustine
    synthesis/purification automated flowsheet.

    :param reactor_type: String descriptor of reactor
    options --> ['PFR', 'CSTR', 'Batch', 'Semibatch']

    :return: kwargs dictionary for the reactor
    """

    # All reactor types will have isothermal --> False,
    # but others will have specific different attributes
    kwargs = {'isothermal': False}

    # Semibatch reactor needs a tank volume
    if reactor_type == 'Semibatch':
        kwargs['vol_tank'] = 0.2  # 200 L or 0.2 m^3

    # PFR needs a diameter of the tube
    if reactor_type == 'PFR':
        kwargs['diam_in'] = 0.0254  # 1 inch in m
        kwargs['num_discr'] = 25  # Number of axial coordinate discr. points

    return kwargs


def get_cryst_kwargs(cryst_type, extra_opts=None):
    """
    Helper function to return a dictionary that will
    be used to define a reactor in the lomustine
    synthesis/purification automated flowsheet.

    :param cryst_type: String descriptor of crystallizer
    options --> ['MSMPR', 'Batch']

    :return:
    """
    kwargs = {'target_comp': 'lom', 'method': '1D-FVM', 'scale': 1e-11}

    if extra_opts is not None:
        for item in extra_opts.items():
            kwargs[item[0]] = item[1]

    return kwargs


def path_constraint(t, y, y_ref, less_than=True, sqrt=False):
    """
    Compute path constraints
    Parameters
    ----------
    t : array or list of arrays
        time array.
    y : array or list of arrays
        time-dependent states. If list, all arrays must have the same number
        of columns.
    y_ref : float or array
        reference value y will be compared to. If array, its first dimension
        should match that of y.
    less_than : bool, optional
        Whether the comparison with y_ref will be less_than or not.
        The default is True.
    Returns
    -------
    constraint : TYPE
        DESCRIPTION.
    """
    t_last = 0
    if isinstance(y, (list, tuple)):
        for a in t:
            a += t_last
            t_last = a[-1]

        t_concat = np.concatenate(t)
        if y[0].ndim == 1:
            y_concat = np.concatenate(y)
        else:
            y_concat = np.vstack(y)
    else:
        t_concat = t
        y_concat = y

    diff = (-1)**(less_than) * (y_ref - y_concat)
    constraint = trapezoidal_rule(t_concat, np.maximum(0, diff)**2)

    if sqrt:
        constraint = np.sqrt(constraint)

    return constraint


def translate_scale(val, bounds):
    """
    Takes a variable from [0, 1] scaling back to it's original state.

    :param val: float, scaled value
    :param bounds: list, of the form [lower_bound, upper_bound]

    :return: unscaled_val, float, the value of the unscaled variable.
    """
    unscaled_val = (1 - val) * bounds[0] + val * bounds[1]

    return unscaled_val

