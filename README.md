# Rocket Pool Twitter Bot

Rocket Pool Twitter bot for daily network stat updates:

```
💰 General 💰
Total Value Locked: Ξ 6097.9050
Staking Pool Balance: Ξ 479.9918

🖥️ Nodes 🖥️
Commission: 15.00%
Registered Nodes: 276
Staking Minipools: 34

🪙 Tokens 🪙
rETH Price: Ξ 1.0045
RPL Price: Ξ 0.0112
Total RPL staked: 405421.19 RPL
Effective RPL staked: 56050.02 RPL
```

Data is pulled from the [Rocket Pool subgraph](https://github.com/Data-Nexus/rocket-pool-mainnet) created by [Data-Nexus](https://github.com/Data-Nexus) and [VGR](https://github.com/VGR-GIT).

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