import numpy as np
from scipy.integrate import cumtrapz
from .data import load_shc
from .data import __get_direction  # TODO move function to more accessible location
from thermo.math.correlate import corr
from scipy import integrate
import os

__author__ = "Alexander Gabourie"
__email__ = "gabourie@stanford.edu"


def __scale_gpumd_tc(vol, T):
    """
    Used to scale the thermal conductivity when converting GPUMD heat-flux correlations
    to thermal conductivity.

    Args:
        vol (float):
            Volume in angstroms^3

        T (float):
            Temperature in K

    Returns:
        float: Converted value
    """

    one = 1.602176634e-19 * 9.651599e7  # eV^3/amu -> Jm^2/s^2*eV
    two = 1. / 1.e15  # fs -> s
    three = 1.e30 / 8.617333262145e-5  # K/(eV*Ang^3) -> K/(eV*m^3) w/ Boltzmann
    return one * two * three / (T * T * vol)


def get_gkma_kappa(data, nbins, nsamples, dt, sample_interval, T=300, vol=1, max_tau=None, directions='xyz',
                   outputfile='heatmode.npy', save=False, directory=None, return_data=True):
    """
    Calculate the Green-Kubo thermal conductivity from modal heat current data from 'load_heatmode'

    Args:
        data (dict):
            Dictionary with heat currents loaded by 'load_heatmode'

        nbins (int):
            Number of bins used during the GPUMD simulation

        nsamples (int):
            Number of times heat flux was sampled with GKMA during GPUMD simulation

        dt (float):
            Time step during data collection in fs

        sample_interval (int):
            Number of time steps per sample of modal heat flux

        T (float):
            Temperature of system during data collection

        vol (float):
            Volume of system in angstroms^3

        max_tau (float):
            Correlation time to calculate up to. Units of ns

        directions (str):
            Directions to gather data from. Any order of 'xyz' is accepted. Excluding directions also allowed (i.e. 'xz'
            is accepted)

        outputfile (str):
            File name to save read data to. Output file is a binary dictionary. Loading from a binary file is much
            faster than re-reading data files and saving is recommended

        save (bool):
            Toggle saving data to binary dictionary. Loading from save file is much faster and recommended (default:
            False)

        directory (str):
            Name of directory storing the input file to read

        return_data (bool):
            Toggle returning the loaded modal heat flux data. If this is False, the user should ensure that
            save is True (default: True)

    Returns:
        dict: Input data dict but with correlation, thermal conductivity, and lag time data included

    """

    if not directory:
        out_path = os.path.join(os.getcwd(), outputfile)
    else:
        out_path = os.path.join(directory, outputfile)

    scale = __scale_gpumd_tc(vol, T)
    # set the heat flux sampling time: rate * timestep * scaling
    srate = sample_interval * dt  # [fs]

    # Calculate total time
    tot_time = srate * (nsamples - 1)  # [fs]

    # set the integration limit (i.e. tau)
    if max_tau is None:
        max_tau = tot_time  # [fs]
    else:
        max_tau = max_tau * 1e6  # [fs]

    max_lag = int(np.floor(max_tau / srate))
    size = max_lag + 1
    data['tau'] = np.squeeze(np.linspace(0, max_lag * srate, max_lag + 1))  # [ns]

    ### AUTOCORRELATION ###
    directions = __get_direction(directions)
    cplx = np.complex128
    # Note: loops necessary due to memory constraints
    #  (can easily max out cluster mem.)
    if 'x' in directions:
        if 'jmxi' not in data.keys() or 'jmxo' not in data.keys():
            raise ValueError("x direction data is missing")

        jx = np.sum(data['jmxi']+data['jmxo'], axis=0)
        data['corr_xmi_x'] = np.zeros((nbins, size))
        data['corr_xmo_x'] = np.zeros((nbins, size))
        data['kmxi'] = np.zeros((nbins, size))
        data['kmxo'] = np.zeros((nbins, size))
        for m in range(nbins):
            data['corr_xmi_x'][m, :] = corr(data['jmxi'][m, :].astype(cplx), jx.astype(cplx), max_lag)
            data['kmxi'][m, :] = integrate.cumtrapz(data['corr_xmi_x'][m, :], data['tau'], initial=0) * scale

            data['corr_xmo_x'][m, :] = corr(data['jmxo'][m, :].astype(cplx), jx.astype(cplx), max_lag)
            data['kmxo'][m, :] = integrate.cumtrapz(data['corr_xmo_x'][m, :], data['tau'], initial=0) * scale
        del jx

    if 'y' in directions:
        if 'jmyi' not in data.keys() or 'jmyo' not in data.keys():
            raise ValueError("y direction data is missing")

        jy = np.sum(data['jmyi']+data['jmyo'], axis=0)
        data['corr_ymi_y'] = np.zeros((nbins, size))
        data['corr_ymo_y'] = np.zeros((nbins, size))
        data['kmyi'] = np.zeros((nbins, size))
        data['kmyo'] = np.zeros((nbins, size))
        for m in range(nbins):
            data['corr_ymi_y'][m, :] = corr(data['jmyi'][m, :].astype(cplx), jy.astype(cplx), max_lag)
            data['kmyi'][m, :] = integrate.cumtrapz(data['corr_ymi_y'][m, :], data['tau'], initial=0) * scale

            data['corr_ymo_y'][m, :] = corr(data['jmyo'][m, :].astype(cplx), jy.astype(cplx), max_lag)
            data['kmyo'][m, :] = integrate.cumtrapz(data['corr_ymo_y'][m, :], data['tau'], initial=0) * scale
        del jy

    if 'z' in directions:
        if 'jmz' not in data.keys():
            raise ValueError("z direction data is missing")

        jz = np.sum(data['jmz'], axis=0)
        data['corr_zm_z'] = np.zeros((nbins, size))
        data['kmz'] = np.zeros((nbins, size))
        for m in range(nbins):
            data['corr_zm_z'][m, :] = corr(data['jmz'][m, :].astype(cplx), jz.astype(cplx), max_lag)
            data['kmz'][m, :] = integrate.cumtrapz(data['corr_zm_z'][m, :], data['tau'], initial=0) * scale
        del jz

    data['tau'] = data['tau'] / 1.e6

    if save:
        np.save(out_path, data)

    if return_data:
        return data
    return


def running_ave(kappa, time):
    """
    Gets running average. Reads and returns the structure input file from GPUMD.

    Args:
        kappa (ndarray): Raw thermal conductivity
        time (ndarray): Time vector that kappa was sampled at

    Returns:
        ndarray: Running average of kappa input
    """
    return cumtrapz(kappa, time, initial=0)/time


def hnemd_spectral_kappa(shc, Fe, T, V):
    """
    Spectral thermal conductivity calculation from an SHC run

    Args:
        shc (dict):
            The data from a single SHC run as output by thermo.gpumd.data.load_shc

        Fe (float):
            HNEMD force in (1/A)

        T (float):
            HNEMD run temperature (in K)

        V (float):
            Volume (A^3) during HNEMD run

    Returns:
        dict: Same as shc argument, but with spectral thermal conductivity included

    Adds the following keys to the shc dictionary:\n
    - k_in (W/m/K/THz)
    - k_out (W/m/K/THz)
    """
    if 'J_in' not in shc.keys() or 'J_out' not in shc.keys():
        raise ValueError("shc argument must be from load_shc and contain in/out heat currents.")

    # ev*A/ps/THz * 1/A^3 *1/K * A ==> W/m/K/THz
    convert = 1602.17662
    shc['k_in'] = shc['J_in']*convert/(Fe*T*V)
    shc['k_out'] = shc['J_out'] * convert / (Fe * T * V)
