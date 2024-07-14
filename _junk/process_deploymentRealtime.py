import logging
import os
import pyglider.ncprocess as ncprocess
import cproofutils.plotting as cpplot
import cproofutils.plotcalvertmap as calmap
import pyglider.slocum as slocum
import numpy as np
import locale

logging.basicConfig(level='INFO')
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

binarydir  = './realtime_raw/'
cacdir     = './cac/'
sensorlist = './dfo-hal1002_sensors.txt'
deploymentyaml = './deploymentRealtime.yml'
l1tsdir    = './L0-timeseries/'
profiledir = './L0-profiles/'
griddir    = './L0-gridfiles/'
plottingyaml = './plottingconfig.yml'
scisuffix    = 'tbd'
glidersuffix = 'sbd'



print(scisuffix)
if True:
    # turn *.EBD and *.DBD into level-1 timeseries netcdf file
    outname = slocum.binary_to_timeseries(binarydir, cacdir, l1tsdir,
        deploymentyaml, search='*183*.[t|s]bd',
        profile_filt_time=400, profile_min_time=100)

fdewdsa
if True:
    # make profile netcdf files for ioos gdac...
    ncprocess.extract_timeseries_profiles(outname, profiledir, deploymentyaml)

if True:
    # make grid of dataset....
    outname2 = ncprocess.make_gridfiles(outname, griddir, deploymentyaml, dz=10)

if True:
    cpplot.grid_plots(outname2, plottingyaml)
    cpplot.timeseries_plots(outname, plottingyaml)
    cpplot.overview_plot(outname2, plottingyaml)
    calmap.plotCalvertMissionMap(latlim=[50, 52.1], lonlim=[-134, -127],
                                start=np.datetime64('2024-07-01'))


