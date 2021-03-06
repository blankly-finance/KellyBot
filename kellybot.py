# -*- coding: utf-8 -*-
"""MultKellyBot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1tmtXjfQ0auFOPVwUjpVL6tVppbCAIdki

In this notebook, we'll use the Blankly package to experiment with a bot based on the Kelly Criterion. The Kelly Criterion deals with position sizing -- given how confident we are in our model's prediction for an asset's behavior, the Kelly Criterion outputs the optimal size for the position.
"""

!pip install blankly #install blankly

"""We'll initialize the basics of our Blankly environment with the command '*blankly init*'. Once done, we get template .json files that we'll need for configuring backtests. Most importantly, we'll need to input our API keys into keys.json. """

!blankly init

"""Here are our imports -- we just need Blankly for this strategy."""

import blankly

"""This section is where we'll initialize the framework for our Kelly price event. We'll create an interface to interact with the exchange as well as set a resolution and download historical data. We'll also estimate our win/loss "probabilities" using a simple RSI bucket strategy. We'll split price movement data into bands of size 10 (RSI 40 to RSI 50 etc.). Then, we'll use the historically observed data to calculate the probability of an increase as well as a win/loss ratio, which we then use to calculate the optimal Kelly size."""

def init_kelly(symbol, state: blankly.StrategyState):
    interface = state.interface
    resolution = state.resolution
    variables = state.variables

    #Get price data
    variables['history'] = interface.history(symbol, 500, resolution, return_as='list')['close']
    rsi = blankly.indicators.rsi(variables['history'])
    '''
    Create RSI buckets, each of which corresponds to a size-10 range of RSI values. 
    '''
    buckets = [[0,0,0,0] for i in range(10)]
    '''For each datapoint, count whether price increases/decreases, size of increase/decrease,
     and put it in appropriate bucket'''
    for i in range(len(variables['history']) - 15):
      r = rsi[i]
      p = variables['history'][i + 15]
      cp = variables['history'][i + 14]
      ind = int(r//10)
      if r < 0:
        ind = 0
      elif r > 90:
        ind = 9
      if cp < p:
        buckets[ind][0]+=1
        buckets[ind][1]+=1
        buckets[ind][3]+=((p - cp)/cp)
      elif cp > p:
        buckets[ind][0]+=0
        buckets[ind][1]+=1
        buckets[ind][2]+=((p - cp)/cp)
    ratios = []
    '''Calculates win/loss ratios'''
    for elem in buckets:
      if elem[0]==0:
        ratios.append(0)
      elif elem[1] - elem[0] == 0:
        ratios.append(1)
      else:
        ratios.append((-elem[3]/elem[0])/(elem[2]/(elem[1] - elem[0])))
    '''Calculates win/loss probabilities'''
    probs = [(elem[0]/elem[1]) if elem[1]!=0 else 0 for elem in buckets]
    '''Calculates Kelly sizing according to formula
    W - (1-W)/R
    '''
    variables['kelly_sizes'] = [max(0,probs[i] - (1-probs[i])/ratios[i]) if ratios[i]!=0 else 0 for i in range(len(probs))]
    print(variables['kelly_sizes'])
    state.variables['owns_position'] = False
    #print(len(variables['history']))
    #print(len(rsi))

"""This section is where we implement the logic of the trading algorithm. After getting the newest price, we calculate the RSI, and based on the observed historical data, we choose how much to scale into the position."""

def price_kelly(price,symbol,state: blankly.StrategyState):
    state.variables['history'].append(price) #Add latest price to current list of data
    '''Here, we pull the data from the last few days, prepare it,
    and run the necessary indicator functions to feed into our model
    '''
    rsi = blankly.indicators.rsi(state.variables['history'])
    '''Clear previous day's position'''
    curr_value = blankly.trunc(state.interface.account[state.base_asset].available, 2) #Amount of asset available
    if curr_value > 0:
      state.interface.market_order(symbol, side='sell', size=curr_value)
    '''Determine bucket based off RSI'''
    ind = int(rsi[-1]//10)
    ind = max(0,ind)
    ind = min(9, ind)
    buy = blankly.trunc(state.variables['kelly_sizes'][ind] * state.interface.cash/price, 2) #Buy appropriate amount
    if buy > 0:
      state.interface.market_order(symbol, side='buy', size=buy)

"""Here's our baseline strategy -- takes the same data and processes it, but every time, we just buy with full amount instead of using Kelly. """

def price_baseline(price,symbol,state: blankly.StrategyState):
    state.variables['history'].append(price) #Add latest price to current list of data
    '''Here, we pull the data from the last few days, prepare it,
    and run the necessary indicator functions to feed into our model
    '''
    rsi = blankly.indicators.rsi(state.variables['history'])
    '''Clear previous day's position'''
    curr_value = blankly.trunc(state.interface.account[state.base_asset].available, 2) #Amount of asset available
    if curr_value > 0:
      state.interface.market_order(symbol, side='sell', size=curr_value)
    '''Determine bucket based off RSI'''
    ind = int(rsi[-1]//10)
    ind = max(0,ind)
    ind = min(9, ind)
    buy = blankly.trunc(int(state.variables['kelly_sizes'][ind]>0.1) * state.interface.cash/price, 2) #Buy appropriate amount
    if buy > 0:
      state.interface.market_order(symbol, side='buy', size=buy)

"""Here, we test our model! We start with $10,000 and connect to Alpaca's API through Blankly. After creating a Blankly strategy and adding our price event, we can run and see the results. We want to compare our strategy's performance to a baseline that just buys and sells as much as possible along the same guidelines as the original strategy."""

# exchange = blankly.Alpaca() #Connect to Alpaca API
# strategy = blankly.Strategy(exchange) #Initialize a Blankly strategy
# strategy.add_price_event(price_baseline, symbol='CRM', resolution='1d', init=init_kelly) #Add our price event and initialization. Using the Kelly initialization is fine.
# strategy.add_price_event(price_baseline, symbol='SPY', resolution='1d', init=init_kelly)
# strategy.add_price_event(price_baseline, symbol='AAPL', resolution='1d', init=init_kelly)
# results = strategy.backtest(to='1y', initial_values={'USD': 10000}) #Backtest one year starting with $10,000
# print(results)

"""When we run our baseline, we see a slight profit along 
with a Sharpe Ratio of 1.29 and Sortino of 1.7 -- decent in terms of reward/risk.
"""

exchange = blankly.Alpaca() #Connect to Alpaca API
strategy = blankly.Strategy(exchange) #Initialize a Blankly strategy
strategy.add_price_event(price_kelly, symbol = 'CRM', resolution = '1d', init = init_kelly)
strategy.add_price_event(price_kelly, symbol='SPY', resolution='1d', init=init_kelly) #Add our price event and initialization
strategy.add_price_event(price_kelly, symbol='AAPL', resolution='1d', init=init_kelly)
results = strategy.backtest(to='1y', initial_values={'USD': 10000}) #Backtest one year starting with $10,000
print(results)

"""In contrast, when we run our Kelly-based allocation model, we end up with a much better reward/risk. We had slightly worse returns with significantly less capital deployed, resulting in a 1.95 Sharpe Ratio and 3.58 Sortino Ratio. We had a solid model before, but adding Kelly allocation really boosted its performance. This model definitely benefited from luck, but the main point is that the Kelly-based RSI model outperformed the naive RSI model. With a more effective model, adding Kelly could result in significantly better performance."""
