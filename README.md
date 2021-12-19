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

2. Install dependencies (currently runs using Python 3.8)
```
pip install -r requirements.txt
```

3. Run the function
```
python bot.py
```
