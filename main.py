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

# %% Load functions from filex
from dc_model import *

# %% Start with temperature data
df = pd.read_csv('temperature.csv')

output = pd.DataFrame()

for i in df.columns:
    output = pd.concat([output,dc_model(df[i])], axis=1)

output.to_csv('output.csv', index=False)