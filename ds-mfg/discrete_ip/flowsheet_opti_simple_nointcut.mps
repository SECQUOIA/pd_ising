* Source:     Pyomo MPS Writer
* Format:     Free MPS
*
NAME unknown
OBJSENSE
 MIN
ROWS
 N  capex
 E  c_e_flow_conservation(n00)_
 E  c_e_flow_conservation(n01)_
 E  c_e_flow_conservation(n02)_
 E  c_e_flow_conservation(n03)_
 E  c_e_flow_conservation(n04)_
 E  c_e_flow_conservation(n05)_
 E  c_e_flow_conservation(n06)_
 E  c_e_flow_conservation(n07)_
 E  c_e_flow_conservation(n08)_
 E  c_e_flow_conservation(n09)_
 E  c_e_flow_conservation(n10)_
 E  c_e_flow_conservation(n11)_
 L  c_u_disjunctions(1)_
 L  c_u_disjunctions(2)_
 L  c_u_disjunctions(3)_
 L  c_u_disjunctions(4)_
 L  c_u_disjunctions(5)_
 G  c_l_continuous_to_batch(1)_
 G  c_l_continuous_to_batch(2)_
 G  c_l_continuous_to_batch(3)_
 G  c_l_continuous_to_batch(4)_
 G  c_l_continuous_to_batch(5)_
 G  c_l_continuous_to_batch(6)_
 G  c_l_continuous_to_batch(7)_
 G  c_l_continuous_to_batch(8)_
COLUMNS
     f(f00) c_e_flow_conservation(n00)_ 1
     f(f00) c_e_flow_conservation(n01)_ 1
     f(f01) capex 0.028899999999999999
     f(f01) c_e_flow_conservation(n01)_ -1
     f(f01) c_e_flow_conservation(n02)_ 1
     f(f01) c_u_disjunctions(2)_ 1
     f(f01) c_l_continuous_to_batch(1)_ -1
     f(f01) c_l_continuous_to_batch(4)_ 1
     f(f02) capex 0.039899999999999998
     f(f02) c_e_flow_conservation(n01)_ -1
     f(f02) c_e_flow_conservation(n02)_ 1
     f(f02) c_u_disjunctions(2)_ 1
     f(f02) c_l_continuous_to_batch(2)_ -1
     f(f02) c_l_continuous_to_batch(4)_ 1
     f(f03) capex 0.1225
     f(f03) c_e_flow_conservation(n01)_ -1
     f(f03) c_e_flow_conservation(n02)_ 1
     f(f03) c_u_disjunctions(2)_ 1
     f(f03) c_l_continuous_to_batch(3)_ -1
     f(f04) c_e_flow_conservation(n02)_ -1
     f(f04) c_e_flow_conservation(n03)_ 1
     f(f05) c_e_flow_conservation(n03)_ -1
     f(f05) c_e_flow_conservation(n04)_ 1
     f(f05) c_u_disjunctions(3)_ 1
     f(f05) c_l_continuous_to_batch(4)_ 1
     f(f05) c_l_continuous_to_batch(5)_ 1
     f(f06) capex 4.9589999999999996
     f(f06) c_e_flow_conservation(n03)_ -1
     f(f06) c_e_flow_conservation(n04)_ 1
     f(f06) c_u_disjunctions(3)_ 1
     f(f06) c_l_continuous_to_batch(1)_ 1
     f(f06) c_l_continuous_to_batch(2)_ 1
     f(f06) c_l_continuous_to_batch(3)_ -1
     f(f07) c_e_flow_conservation(n04)_ -1
     f(f07) c_e_flow_conservation(n05)_ 1
     f(f08) capex 6.1929999999999996
     f(f08) c_e_flow_conservation(n05)_ -1
     f(f08) c_e_flow_conservation(n06)_ 1
     f(f08) c_u_disjunctions(4)_ 1
     f(f09) capex 9.7170000000000005
     f(f09) c_e_flow_conservation(n05)_ -1
     f(f09) c_e_flow_conservation(n06)_ 1
     f(f09) c_u_disjunctions(4)_ 1
     f(f10) capex 3.3519999999999999
     f(f10) c_e_flow_conservation(n05)_ -1
     f(f10) c_e_flow_conservation(n06)_ 1
     f(f10) c_u_disjunctions(4)_ 1
     f(f10) c_l_continuous_to_batch(1)_ -1
     f(f10) c_l_continuous_to_batch(2)_ -1
     f(f10) c_l_continuous_to_batch(3)_ -1
     f(f10) c_l_continuous_to_batch(5)_ 1
     f(f11) capex 6.1630000000000003
     f(f11) c_e_flow_conservation(n06)_ -1
     f(f11) c_e_flow_conservation(n07)_ 1
     f(f12) c_e_flow_conservation(n07)_ -1
     f(f12) c_e_flow_conservation(n08)_ 1
     f(f13) capex 0.73899999999999999
     f(f13) c_e_flow_conservation(n08)_ -1
     f(f13) c_e_flow_conservation(n09)_ 1
     f(f13) c_u_disjunctions(5)_ 1
     f(f13) c_l_continuous_to_batch(6)_ -1
     f(f14) capex 0.83999999999999997
     f(f14) c_e_flow_conservation(n08)_ -1
     f(f14) c_e_flow_conservation(n09)_ 1
     f(f14) c_u_disjunctions(5)_ 1
     f(f14) c_l_continuous_to_batch(7)_ -1
     f(f15) capex 1.2709999999999999
     f(f15) c_e_flow_conservation(n08)_ -1
     f(f15) c_e_flow_conservation(n09)_ 1
     f(f15) c_u_disjunctions(5)_ 1
     f(f15) c_l_continuous_to_batch(8)_ -1
     f(f16) capex 6.9900000000000002
     f(f16) c_e_flow_conservation(n07)_ -1
     f(f16) c_e_flow_conservation(n10)_ 1
     f(f16) c_u_disjunctions(1)_ 1
     f(f16) c_u_disjunctions(5)_ 1
     f(f17) capex 1.333
     f(f17) c_e_flow_conservation(n09)_ -1
     f(f17) c_e_flow_conservation(n10)_ 1
     f(f17) c_u_disjunctions(1)_ 1
     f(f17) c_l_continuous_to_batch(6)_ 1
     f(f17) c_l_continuous_to_batch(7)_ 1
     f(f17) c_l_continuous_to_batch(8)_ 1
     f(f18) c_e_flow_conservation(n10)_ -1
     f(f18) c_e_flow_conservation(n11)_ 1
RHS
     RHS c_e_flow_conservation(n00)_ 1
     RHS c_e_flow_conservation(n01)_ 0
     RHS c_e_flow_conservation(n02)_ 0
     RHS c_e_flow_conservation(n03)_ 0
     RHS c_e_flow_conservation(n04)_ 0
     RHS c_e_flow_conservation(n05)_ 0
     RHS c_e_flow_conservation(n06)_ 0
     RHS c_e_flow_conservation(n07)_ 0
     RHS c_e_flow_conservation(n08)_ 0
     RHS c_e_flow_conservation(n09)_ 0
     RHS c_e_flow_conservation(n10)_ 0
     RHS c_e_flow_conservation(n11)_ 1
     RHS c_u_disjunctions(1)_ 1
     RHS c_u_disjunctions(2)_ 1
     RHS c_u_disjunctions(3)_ 1
     RHS c_u_disjunctions(4)_ 1
     RHS c_u_disjunctions(5)_ 1
     RHS c_l_continuous_to_batch(1)_ -1
     RHS c_l_continuous_to_batch(2)_ -1
     RHS c_l_continuous_to_batch(3)_ -2
     RHS c_l_continuous_to_batch(4)_ 1
     RHS c_l_continuous_to_batch(5)_ 1
     RHS c_l_continuous_to_batch(6)_ 0
     RHS c_l_continuous_to_batch(7)_ 0
     RHS c_l_continuous_to_batch(8)_ 0
BOUNDS
 BV BOUND f(f00)
 BV BOUND f(f01)
 BV BOUND f(f02)
 BV BOUND f(f03)
 BV BOUND f(f04)
 BV BOUND f(f05)
 BV BOUND f(f06)
 BV BOUND f(f07)
 BV BOUND f(f08)
 BV BOUND f(f09)
 BV BOUND f(f10)
 BV BOUND f(f11)
 BV BOUND f(f12)
 BV BOUND f(f13)
 BV BOUND f(f14)
 BV BOUND f(f15)
 BV BOUND f(f16)
 BV BOUND f(f17)
 BV BOUND f(f18)
ENDATA
