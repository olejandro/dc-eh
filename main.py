# -*- coding: utf-8 -*-
"""
Created on Sun Aug  9 22:03:20 2020

@author: Olex
"""

# %% Import required packages
import os
import pandas as pd
import xlrd

# %% Set working directory
# Return absolute path to this file
absolute_path = os.path.abspath(__file__)
# Change working directory to this file's directory
os.chdir(os.path.dirname(absolute_path))

# %% General Assumptions
# Most of the assumptions are from page 171 of deliverable 4.5 of RenewIT

# c_p air [MJ/(kg*K)]
c_p_air = 1.005/1000
# air density [kg/m3]
air_density = 1.2
# Q_IT_max [MW]
q_it_max = 1
# Delta_T_IT [°C]
delta_t_it = 15
# T_DC_sup [°C]
t_dc_sup = 20
# Delta_T_PP [°C]
delta_t_pp = 3
# Max outdoor temp. for IASE [°C]
iase_t_outdoor_max = t_dc_sup - delta_t_pp
# Airflow by-pass
airflow_bypass = 0.1
# Fan efficiency (incl. Motor)
fan_efficiency = 0.75
# V_DC_max [m3/s]
v_dc_max = q_it_max / (air_density * c_p_air * delta_t_it) / (1 - airflow_bypass)
# V_OA_max [m3/s]
v_oa_max = v_dc_max
# Delta_p_fan_OA_max [Pa]
delta_p_fan_oa_max = 350
# Delta_p_IASE_max [Pa]
delta_p_iase_max = 400
# Delta_p_fan_CRAH_max [Pa]
delta_p_fan_crah_max = 700
# Outlet heat source temp at HP evaporator [°C]
t_heat_source_hp_evap = 20

# %% Workload profile

workload_profile = (
    0.53,
    0.5,
    0.49,
    0.49,
    0.49,
    0.53,
    0.58,
    0.58,
    0.63,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.68,
    0.63,
    0.58,
    0.53
    )

# %% Build df

# Start with temperature data
dc_df = pd.read_csv('temperature.csv')
# Add the workload profile repeated 365 times
dc_df = dc_df.assign(it_load=(workload_profile * 365))
#
dc_df = dc_df.assign(
    # Indirect Air Side Economization
    iase=lambda x: x['t_outdoor'] < iase_t_outdoor_max,
    # All the power absorbed by the IT components is assumed to be converted
    # into heat
    q_it=lambda x: x['it_load'] * q_it_max,
    # The airflow strictly needed to cool down the IT equipment
    v_it=lambda x: x['q_it'] / (air_density * c_p_air * delta_t_it),
    # The airflow recirculating inside the data hall (v_dc > v_it)
    v_dc=lambda x: x['v_it'] / (1 - airflow_bypass),
    # Power absorbed by the fan of Computer Room Air Handler
    p_fan_crah=lambda x: (v_dc_max * delta_p_fan_crah_max / 10 ** 6
                          / fan_efficiency * (x['v_dc'] / v_dc_max) ** 2.5),
    # Power absorbed by the fan for pushing air through economizer
    p_fan_iase=lambda x: (v_dc_max * delta_p_iase_max / 10 ** 6 / fan_efficiency
                          * (x['v_dc'] / v_dc_max) ** 2.5 * x['iase']),
    # Supply temperature for cooling IT equipment is fixed
    t_it_in=lambda x: (t_dc_sup + (1 - fan_efficiency) * x['p_fan_crah']
                       / (x['v_dc'] * air_density * c_p_air)),
    # Temperature increase through IT equipment is assumed constant
    t_it_out=lambda x: x['t_it_in'] + delta_t_it,
    # This temperature is slightly lower than the previous due to some air
    # that by-passes the IT equipment (and remains cool)
    t_dc_ret=lambda x: ((1 - airflow_bypass) * x['t_it_out'] + airflow_bypass
                        * x['t_it_in'] + (1 - fan_efficiency) * x['p_fan_iase']
                        / (x['v_dc'] * air_density * c_p_air)),
    # The outdoor air heats up when cooling the air inside the DC through the
    # economizer
    t_hx_oa_out=lambda x: x['iase'] * (x['t_dc_ret'] - delta_t_pp),
    # Airflow of outdoor air to be taken from environment
    v_oa=lambda x: x['iase'] * (x['v_dc'] * (x['t_dc_ret'] - t_dc_sup)
                                / (x['t_hx_oa_out'] - x['t_outdoor'])),
    # Power absorbed by the fan for withdrawing outdoor air. The efficiency of
    # the fan is not constant when the load is reduced. Following the
    # indication reported on RenewIT (deliverable 4.5) the power draw is
    # proportonal to the airflow at 2.5 power (instead of 3rd power as expected
    # by theoretical assumptions)
    p_fan_oa=lambda x: (v_oa_max * delta_p_fan_oa_max / 10 ** 6 / fan_efficiency
                        * (x['v_oa'] / v_oa_max) ** 2.5),
    # COP of the chiller plant (including the water pumps and the cooling tower)
    # is expressed as a function of the outdoor air using the values indicated
    # by Depoorter and Oro
    p_chiller=lambda x: (x['v_dc'] * air_density * c_p_air * (x['t_dc_ret']
                                                              - t_dc_sup)
                         / (0.0000108201 * x['t_outdoor'] ** 3 - 0.000805206
                            * x['t_outdoor'] ** 2 - 0.0622451 * x['t_outdoor']
                            + 5.82023) * (x['v_oa'] == 0)),
    # Power consumption of cooling system
    p_cooling=lambda x: (x['p_fan_crah'] + x['p_fan_iase'] + x['p_fan_oa']
                         + x['p_chiller']),
    # Hp: when in free cooling mode, this airflow is equal to volume of air taken
    # from the external environment and heated up through the economizer.
    # When the chiller is working, instead, the airflow used to cool down in the
    # cooling tower is assumed equal to the maximum airflow in free cooling mode
    exhausted_hot_airflow=lambda x: (x['iase'] * x['v_oa']
                                     + (1 - x['iase']) * v_oa_max),
    # In free cooling mode it coincides with T_HX_OA_out (the increase of
    # temperature due to the fan can be neglected even if it's included in the formula).
    # When the chiller is used the exhausted air temperature is calculated
    # knowing the fixed airflow through the chiller and the initial outdoor air
    # temperature.
    t_exhausted_air=lambda x: (x['iase']
                               * (x['t_hx_oa_out'] + (1 - fan_efficiency)
                                  * x['p_fan_oa'] / (x['exhausted_hot_airflow']
                                                     * air_density * c_p_air))
                               + (1 - x['iase'])
                               * (x['t_outdoor'] + ((x['v_dc'] * air_density
                                                    * c_p_air)
                                  * (x['t_dc_ret'] - t_dc_sup) + x['p_chiller'])
                               / (x['exhausted_hot_airflow'] * air_density
                                  * c_p_air))),
    # This heat is calculated assuming that the exhausted air can be cooled
    # down to 20°C.
    # Due to the low temperature of this heat, it is sent to a HP for upgrading
    # and injection in DH.
    heat_at_hp_evaporator=lambda x: (x['exhausted_hot_airflow'] * air_density
                                     * c_p_air * (x['t_exhausted_air']
                                                  - t_heat_source_hp_evap)
                                     * (x['t_exhausted_air']
                                        >= t_heat_source_hp_evap))
    )