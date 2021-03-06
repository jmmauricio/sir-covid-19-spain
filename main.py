import os
import requests

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy import optimize
from scipy.integrate import odeint

if not os.path.exists("data"):
    os.makedirs("data")

if not os.path.exists("images"):
    os.makedirs("images")

# download file

url = "https://covid19.isciii.es/resources/serie_historica_acumulados.csv"
s = requests.get(url).text

# save file

fn = os.path.join("data","serie_historica_acumulados.csv")
with open(fn, "w") as f:
    f.write(s)

# read file

df = pd.read_csv(fn, encoding="latin1")

# prepare

df = df[:-1]
df = df.fillna(0)
df.columns = ["ccaa", "date", "cases", "hospitalized", "uci", "dead"]
df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")

dft = df[["date", "cases", "hospitalized", "uci", "dead"]].groupby("date").sum()
dfp = df.pivot(index="date", columns="ccaa", values="cases")

dfpct = 100*dft["dead"]/dft["cases"]
dft["infected"] = dft["hospitalized"] + dft["uci"]
dft["recovered"] = dft["cases"] - dft["infected"]

# optimization SIR

def sir(N, beta, gamma, days):
    I0 = 1
    R0 = 0
    S0 = N - I0 - R0
    def deriv(y, t, N, beta, gamma):
        S, I, R = y
        dSdt = -beta * S * I / N
        dIdt = beta * S * I / N - gamma * I
        dRdt = gamma * I
        return dSdt, dIdt, dRdt
    y0 = S0, I0, R0
    t = np.linspace(0, days, days)
    ret = odeint(deriv, y0, t, args=(N, beta, gamma))
    S, I, R = ret.T
    return S, I, R

def fdelay(delay):
    def f(x):
        N = x[0]
        beta = x[1]
        gamma = x[2]
        days = len(dft)
        S, I, R = sir(N, beta, gamma, days + abs(delay)*2)
        lim = abs(delay) + delay
        S, I, R = S[lim:lim+days], I[lim:lim+days], R[lim:lim+days]
        Io, Ro = dft["infected"].values, dft["recovered"].values
        So = N - Io
        #loss = ((S - So)**2).sum()/days + ((I - Io)**2).sum()/days + ((R - Ro)**2).sum()/days
        loss = ((I - Io)**2).sum()/days + ((R - Ro)**2).sum()/days
        return loss
    result = optimize.minimize(f, [80000, 1, 1], method="Nelder-Mead")
    return result

delay = 0
result = fdelay(delay)
for d in range(-15, 15):
    r2 = fdelay(d)
    print("delay: {}, fun: {}".format(d, r2.fun))
    if r2.fun < result.fun:
        delay = d
        result = r2

N = result.x[0]
beta = result.x[1]
gamma = result.x[2]
days = len(dft)

print("optimal: N = {}, beta = {}, gamma = {}, delay = {}".format(N, beta, gamma, delay))
print("error: {}".format(result.fun))

S, I, R =  sir(N, beta, gamma, days + abs(delay)*2)
lim = abs(delay) + delay
S, I, R = S[lim:lim+days], I[lim:lim+days], R[lim:lim+days]

dft["S"] = S
dft["I"] = I
dft["R"] = R

dft["susceptible"] = N - dft["infected"]

# future

far = 60 # days

S, I, R =  sir(N, beta, gamma, days+far + abs(delay)*2)
lim = abs(delay) + delay
S, I, R = S[lim:lim+days+far], I[lim:lim+days+far], R[lim:lim+days+far]
d = {
    "S": S,
    "I": I,
    "R": R,
    "susceptible": list(dft["susceptible"].values) + [np.nan]*far,
    "infected": list(dft["infected"].values) + [np.nan]*far,
    "recovered": list(dft["recovered"].values) + [np.nan]*far,
}
dff = pd.DataFrame(d)
dff["date"] = pd.date_range(dft.index[0],periods=days+far,freq="D")
dff = dff.set_index("date")

# graph

fig, ax = plt.subplots(figsize=(8,6))
dfp.plot(ax=ax)
ax.set_title("CCAA")
ax.grid(True, which="both")
dfp.to_csv(os.path.join("data", "generated-ccaa.csv"))
plt.savefig(os.path.join("images", "generated-ccaa.png"), format="png", dpi=300)
plt.savefig(os.path.join("images", "generated-ccaa.pdf"), format="pdf", dpi=300)

fig, ax = plt.subplots(figsize=(8,6))
dft[["cases", "hospitalized", "uci", "dead"]].plot(ax=ax)
ax.set_title("Total")
ax.grid(True, which="both")
dft[["cases", "hospitalized", "uci", "dead"]].to_csv(os.path.join("data", "generated-total.csv"))
plt.savefig(os.path.join("images", "generated-total.png"), format="png", dpi=300)
plt.savefig(os.path.join("images", "generated-total.pdf"), format="pdf", dpi=300)

fig, ax = plt.subplots(figsize=(8,6))
dfpct.plot(ax=ax)
ax.set_title("% Dead")
ax.grid(True, which="both")
plt.savefig(os.path.join("images", "generated-deadpct.png"), format="png", dpi=300)
plt.savefig(os.path.join("images", "generated-deadpct.pdf"), format="pdf", dpi=300)

fig, ax = plt.subplots(figsize=(8,6))
dff[["susceptible", "infected", "recovered"]].plot(ax=ax)
dff[["S", "I", "R"]].plot(ax=ax, linestyle=":")
ax.set_title("SIR Model")
ax.grid(True, which="both")
dff.to_csv(os.path.join("data", "generated-sir.csv"))
plt.savefig(os.path.join("images", "generated-sir.png"), format="png", dpi=300)
plt.savefig(os.path.join("images", "generated-sir.pdf"), format="pdf", dpi=300)

# case forecasting

dff["cases"] = dff["recovered"] + dff["infected"]
dff["forecast"] = dff["R"] + dff["I"]
dff[["forecast", "cases"]].to_csv(os.path.join("data", "generated-cases.csv"))


fig, ax = plt.subplots(figsize=(8,6))
dff[["cases"]].plot(ax=ax)
dff[["forecast"]].plot(ax=ax, linestyle=":")
ax.set_title("SIR Model")
ax.grid(True, which="both")
plt.savefig(os.path.join("images", "generated-sir-cases.png"), format="png", dpi=300)
plt.savefig(os.path.join("images", "generated-sir-cases.pdf"), format="pdf", dpi=300)