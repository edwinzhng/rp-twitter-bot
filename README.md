# Rocket Pool Twitter Bot

[Twitter @RocketPoolBot](https://twitter.com/RocketPoolBot)

Rocket Pool Twitter bot for daily network stat updates:

```
💰 General
TVL: Ξ 11.14k ($48.1M)
Staking Pool Balance: Ξ 1.18k

🖥️ Nodes
Commission: 15.00%
Registered Nodes: 347
Staking Minipools: 95
ETH Validator Share: 0.037%

🪙 Tokens
rETH Price: Ξ 1.0050
RPL Price: Ξ 0.0109
RPL staked: 637.3k RPL
Effective RPL staked: 141.9k RPL
```

Rocket Pool Data is pulled from the [Rocket Pool subgraph](https://github.com/Data-Nexus/rocket-pool-mainnet) created by [Data-Nexus](https://github.com/Data-Nexus) and [VGR](https://github.com/VGR-GIT).

The current ETH/USD price is taken from [CoinGecko](https://www.coingecko.com/), and total number of ETH validators is from [Beaconcha.in](https://beaconcha.in/).

## Development

1. Copy `.env.sample` into a new file called `.env` and set the values to your Twitter API keys
```
cp .env.sample .env
```

2. Run the function using `python run_local.py`

## Deployment

1. Build the Lambda function + layer using `./build.sh [PYTHON_VERSION]` (currently uses Python 3.8)
```
./build.sh 3.8
```

2. Upload build files to Lambda and set up hourly schedule using EventBridge

## Attributions

General bot setup is taken from [dylanjcastillo/twitter-bot-python-aws-lambda](https://github.com/dylanjcastillo/twitter-bot-python-aws-lambda).