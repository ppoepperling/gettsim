# -*- coding: utf-8 -*-
"""
TAX TRANSFER SYSTEM FOR UBI
Eric Sommer, 2018
"""
from imports import aggr
from termcolor import colored, cprint
from tax_transfer import soc_ins_contrib, pensions, zve, tax_sched
from tax_transfer import soli, favorability_check, uhv

import pandas as pd

# from numba import jit


def tax_transfer_ubi(df, datayear, taxyear, tb, tb_pens=[], mw=[], hyporun=False):
    """Counterfactual with Unconditional Basic income

    Either uses the functions from the baseline system (tax_transfer.py)
    or redefines the respective element

    - Basic guidelines:
        1. UBI replaces ALG2, Social assistance, Kindergeld, Wohngeld, Kinderzuschlag
        2. UBI is a flat rate, possibly lower for kids below a certain age.
        3. UBI is not means-tested and does not depend on family composition
        4. UBI is fully taxable
        5. Possibly, also abolish midi and mini job rules.


    Arguments:

        - *df*: Input Data Frame
        - *datayear*: year of SOEP wave
        - *taxyear*: year of reform baseline
        - *tb*: dictionary with tax-benefit parameters
        - *tb_pens*: Parameters for pension calculations
        - *mw*: Mean earnings by year, for pension calculations.
        - *hyporun*: indicator for hypothetical household input (defult: use real SOEP data)


    """

    # Social Insurance Contributions
    df = df.join(
        other=soc_ins_contrib(
            df[
                [
                    "pid",
                    "hid",
                    "east",
                    "m_wage",
                    "selfemployed",
                    "m_self",
                    "m_pensions",
                    "age",
                    "haskids",
                    "pkv",
                ]
            ],
            tb,
            taxyear,
        ),
        how="inner",
    )

    # Unemployment benefits
    df["m_alg1"] = 0

    # Pension benefits
    df["pen_sim"] = pensions(df, tb, tb_pens, mw, taxyear, hyporun)

    # UBI
    df["ubi"] = ubi(df, tb)
    # aggregate it on hh level
    df["ubi_hh"] = aggr(df, "ubi", "all_hh")
    # Income Tax
    taxvars = [
        "pid",
        "hid",
        "female",
        "head_tu",
        "tu_id",
        "east",
        "m_wage",
        "selfemployed",
        "m_self",
        "m_pensions",
        "age",
        "pkv",
        "zveranl",
        "child",
        "child_num",
        "renteneintritt",
        "w_hours",
        "m_kapinc",
        "m_vermiet",
        "m_imputedrent",
        "marstat",
        "handcap_dummy",
        "handcap_degree",
        "rvbeit",
        "gkvbeit",
        "pvbeit",
        "avbeit",
        "adult_num_tu",
        "child_num_tu",
        "alleinerz",
        "ineducation",
        "ubi",
    ]

    # 5.1 Calculate Taxable income (zve = zu versteuerndes Einkommen)
    df = df.join(other=zve(df[taxvars], tb, taxyear, hyporun, ref="UBI"), how="inner")

    # 5.2 Apply Tax Schedule
    df = df.join(other=tax_sched(df, tb, taxyear), how="inner")

    # 5.3 Child benefit (Kindergeld). Yes, this belongs to Income Tax
    df["kindergeld_basis"] = 0
    df["kindergeld_tu_basis"] = 0

    # 5.4 Günstigerprüfung to obtain final income tax due.
    # different call here, because 'kindergeld' is overwritten by the function and
    # needs to be updated. not really elegant I must admit...
    temp = favorability_check(df, tb, taxyear)
    for var in [["incometax_tu", "kindergeld", "kindergeld_hh", "kindergeld_tu"]]:
        df[var] = temp[var]
    df["tu_id"].describe()
    # 5.5 Solidarity Surcharge
    df = df.join(other=soli(df, tb, taxyear), how="inner")

    # 6. SOCIAL TRANSFERS / BENEFITS
    # 6.0.1 Alimony Advance (Unterhaltsvorschuss)
    df["uhv"] = uhv(df, tb, taxyear)
    df["uhv_hh"] = aggr(df, "uhv", "all_hh")

    # 6.1. Wohngeld, Housing Benefit
    df["wohngeld"] = 0
    # 6.2 ALG2, Basic Unemployment Benefit
    df["m_alg2"] = 0

    # 6.3. Kinderzuschlag, Additional Child Benefit
    df["kiz"] = 0

    # 7. Drop unnecessary variables. not necessary anymore.s
    # df = dropstuff(df)

    # 8. Finally, calculate disposable income
    # To be updated!
    df["dpi_ind"] = df[
        [
            "m_wage",
            "m_kapinc",
            "m_self",
            "m_vermiet",
            "m_imputedrent",
            "m_pensions",
            "m_transfers",
            "ubi",
            "uhv",
        ]
    ].sum(axis=1) - df[
        ["incometax", "soli", "abgst", "gkvbeit", "rvbeit", "pvbeit", "avbeit"]
    ].sum(
        axis=1
    )

    df["dpi_ind_temp"] = df.groupby(["hid"])["dpi_ind"].transform(sum)

    # There are no benefits at the household level
    df["dpi"] = df["dpi_ind_temp"]

    return df


def ubi(df, tb):
    ubi = pd.DataFrame(index=df.index.copy())
    # ubi["hid"] = df["hid"]
    ubi["ubi"] = 0
    ubi.loc[df["age"] >= 18, "ubi"] = tb["ubi_adult"]
    ubi.loc[df["age"] < 18, "ubi"] = tb["ubi_child"]

    # ubi['ubi_hh'] = aggr(ubi, 'ubi', True)

    return ubi["ubi"]
