# Rocket Pool Twitter Bot

Rocket Pool Twitter bot for daily network stat updates

This bot tweets output similar to `rocketpool network stats` from the
[smartnode CLI](https://github.com/rocket-pool/smartnode):

```
========== General Stats ==========
Total Value Locked:      4306.428862 ETH
Staking Pool Balance:    259.831000 ETH
Minipool Queue Demand:   0.000000 ETH
Staking Pool ETH Used:   34.443863%

============== Nodes ==============
Current Commission Rate: 15.000000%
Node Count:              219
Active Minipools:        35
    Initialized:         0
    Prelaunch:           7
    Staking:             28
    Withdrawable:        0
    Dissolved:           0
Inactive Minipools:      0

============== Tokens =============
rETH Price (ETH / rETH): 1.004352 ETH
RPL Price (ETH / RPL):   0.011313 ETH
Total RPL staked:        258704.257817 RPL
Effective RPL staked:    43849.595604 RPL
```

## Development

1. Copy `.env.sample` into a new file called `.env` and set the values to your Twitter API keys
```
cp .env.sample .env
```

2. TODO
