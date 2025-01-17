#!/usr/bin/env python
"""The PROSPECT leaf optical properties model
Versions 5, D, and PRO
"""
import numpy as np
from scipy.special import expi
import os

current_directory = os.getcwd()

# PROSPECT-D absorption coefficients
prospectd_path = os.path.join(current_directory, 'models/prospect/prospectd_absc.txt')
_, nr_d, kab_d, kcar_d, kant_d, kbrown_d, kw_d, km_d = np.loadtxt(prospectd_path, unpack=True)

# PROSPECT-5 absorption coefficients
prospect5_path = os.path.join(current_directory, 'models/prospect/prospect5_absc.txt')
nr_5, kab_5, kcar_5, kbrown_5, kw_5, km_5 = np.loadtxt(prospect5_path, unpack=True)

def calctav ( alpha, nr):
    #***********************************************************************
    #calctav
    # ***********************************************************************
    # Stern F. (1964), Transmission of isotropic radiation across an
    # interface between two dielectrics, Appl. Opt., 3(1):111-113.
    # Allen W.A. (1973), Transmission of isotropic light across a
    # dielectric surface in two and three dimensions, J. Opt. Soc. Am.,
    # 63(6):664-666.
    # ***********************************************************************
    

    #rd  = pi/180 np.deg2rad
    n2  = nr*nr
    npx  = n2+1
    nm  = n2-1
    a   = (nr+1)*(nr+1)/2.
    k   = -(n2-1)*(n2-1)/4.
    sa  = np.sin(np.deg2rad(alpha))
    
    if alpha != 90:
        b1 = np.sqrt((sa*sa-npx/2)*(sa*sa-npx/2)+k)
    else:
        b1 = 0.
    b2 = sa*sa - npx/2
    b   = b1-b2
    b3  = b**3
    a3  = a**3
    ts  = (k**2/(6*b3)+k/b-b/2)-(k**2./(6*a3)+k/a-a/2)

    tp1 = -2*n2*(b-a)/(npx**2)
    tp2 = -2*n2*npx*np.log(b/a)/(nm**2)
    tp3 = n2*(1/b-1/a)/2
    tp4 = 16*n2**2*(n2**2+1)*np.log((2*npx*b-nm**2)/(2*npx*a-nm**2))/(npx**3*nm**2)
    tp5 = 16*n2**3*(1./(2*npx*b-nm**2)-1/(2*npx*a-nm**2))/(npx**3)
    tp  = tp1+tp2+tp3+tp4+tp5
    tav = (ts+tp)/(2*sa**2)

    return tav


def refl_trans_one_layer (alpha, nr, tau):
    # ***********************************************************************
    # reflectance and transmittance of one layer
    # ***********************************************************************
    # Allen W.A., Gausman H.W., Richardson A.J., Thomas J.R. (1969),
    # Interaction of isotropic ligth with a compact plant leaf, J. Opt.
    # Soc. Am., 59(10):1376-1379.
    # ***********************************************************************
    # reflectivity and transmissivity at the interface
    #-------------------------------------------------   
    talf = calctav (alpha,nr)
    ralf = 1.0-talf
    t12 = calctav (90,nr)
    r12 = 1. - t12
    t21 = t12/(nr*nr)
    r21 = 1-t21

    # top surface side
    denom = 1. - r21*r21*tau*tau
    Ta = talf*tau*t21/denom
    Ra = ralf + r21*tau*Ta

    # bottom surface side
    t = t12*tau*t21/denom
    r = r12+r21*tau*t
    
    return r, t, Ra, Ta, denom

def prospectdcore (N, cab, car, cbrown, cw, cm, ant,
            nr, kab, kcar, kbrown, kw, km, kant,
            alpha=40.):

    lambdas = np.arange(400, 2501) # wavelengths
    n_lambdas = len(lambdas)
    n_elems_list = [len(spectrum)  for spectrum in 
                [nr, kab, kcar, kbrown, kw, km, kant]]
    if not all(n_elems == n_lambdas for n_elems in n_elems_list):
        raise ValueError("Leaf spectra don't have the right shape!")
    
    kall = (cab*kab + car*kcar + ant*kant + cbrown*kbrown +
            cw*kw + cm*km)/N
    j = kall > 0
    t1 = (1-kall)*np.exp(-kall)
    t2 = kall**2*(-expi(-kall))
    tau = np.ones_like(t1)
    tau[j] = t1[j] + t2[j]

    r, t, Ra, Ta, denom = refl_trans_one_layer (alpha, nr, tau)

    # ***********************************************************************
    # reflectance and transmittance of N layers
    # Stokes equations to compute properties of next N-1 layers (N real)
    # Normal case
    # ***********************************************************************
    # Stokes G.G. (1862), On the intensity of the light reflected from
    # or transmitted through a pile of plates, Proc. Roy. Soc. Lond.,
    # 11:545-556.
    # ***********************************************************************
    D       = np.sqrt((1+r+t)*(1+r-t)*(1.-r+t)*(1.-r-t))
    rq      = r*r
    tq      = t*t
    a       = (1+rq-tq+D)/(2*r)
    b       = (1-rq+tq+D)/(2*t)

    bNm1    = np.power(b, N-1)
    bN2     = bNm1*bNm1
    a2      = a*a
    denom   = a2*bN2-1
    Rsub    = a*(bN2-1)/denom
    Tsub    = bNm1*(a2-1)/denom

    # Case of zero absorption
    j       = r+t >= 1.
    Tsub[j] = t[j]/(t[j]+(1-t[j])*(N-1))
    Rsub[j] = 1-Tsub[j]

    # Reflectance and transmittance of the leaf: combine top layer with next N-1 layers
    denom   = 1-Rsub*r
    tran    = Ta*Tsub/denom
    refl    = Ra+Ta*Rsub*t/denom

    return lambdas, refl, tran


def run_prospect(n, cab, car, cbrown, cw, cm, ant=0.0,
                 prospect_version="D",
                 nr=None, kab=None, kcar=None, kbrown=None, kw=None,
                 km=None, kant=None, alpha=40.):
    """The PROSPECT model, versions 5 and D"""

    if prospect_version == "5":
        # Call the original PROSPECT-5. In case the user has supplied
        # spectra, use them.
        wv, refl, trans = prospectdcore(n, cab, car, cbrown, cw, cm, 0.0,
                                     nr_5 if nr is None else nr,
                                     kab_5 if kab is None else kab,
                                     kcar_5 if kcar is None else kcar,
                                     kbrown_5 if kbrown is None else kbrown,
                                     kw_5 if kw is None else kw,
                                     km_5 if km is None else km,
                                     np.zeros_like(km_5),
                                     alpha=alpha)
    elif prospect_version.upper() == "D":
        wv, refl, trans = prospectdcore(n, cab, car, cbrown, cw, cm, ant,
                                     nr_d if nr is None else nr,
                                     kab_d if kab is None else kab,
                                     kcar_d if kcar is None else kcar,
                                     kbrown_d if kbrown is None else kbrown,
                                     kw_d if kw is None else kw,
                                     km_d if km is None else km,
                                     kant_d if kant is None else kant,
                                     alpha=alpha)
    else:
        raise ValueError("prospect_version can only be 5 or D!")

    return wv, refl, trans

