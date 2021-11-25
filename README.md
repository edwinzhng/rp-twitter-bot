# Rocket Pool Twitter Bot

Rocket Pool Twitter bot [@RocketPoolBot](https://twitter.com/RocketPoolBot) for daily network stat updates:

[![github-readme-twitter](https://github-readme-twitter.gazf.vercel.app/api?id=RocketPoolBot)](https://twitter.com/RocketPoolBot)

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
