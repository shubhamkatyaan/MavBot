# MavBot

MavBot is a Python-based bot designed to monitor cryptocurrency tokens by fetching data from various APIs, analyzing token information, and sending notifications via Telegram. The bot processes tokens listed in shard files and retrieves data such as token prices, market capitalization, and volume. It also calculates the number of holders for each token and sends this information to a specified Telegram chat.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [APIs Used](#apis-used)
- [File Breakdown](#file-breakdown)
- [Logging and Debugging](#logging-and-debugging)
- [Future Enhancements](#future-enhancements)
- [License](#license)

## Features
- **Token Monitoring**: Reads token addresses from shard files and fetches their data.
- **Data Retrieval**: Utilizes APIs like CoinGecko and GeckoTerminal to obtain token information.
- **Holder Calculation**: Computes the number of holders for each token based on the fetched data.
- **Telegram Notifications**: Sends token information and holder counts to a Telegram chat.
- **Parallel Processing**: Handles multiple token shards efficiently.
- **Error Handling**: Ensures API rate limits and failures do not crash the bot.

## Installation

### Prerequisites
Ensure you have the following installed:
- Python 3.8+
- Pip (Python Package Manager)
- Required dependencies from `requirements.txt`

### Steps to Install
1. Clone the repository:
   ```sh
   git clone https://github.com/shubhamkatyaan/MavBot.git
   cd MavBot
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Set up environment variables in a `.env` file.

## Configuration
### Environment Variables
Create a `.env` file with the following values:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```
### Shard Files
Ensure that shard files containing token addresses are present in the `shards/` directory. The bot reads from these files to monitor specific tokens.

## Usage
To run the bot:
```sh
python bot.py
```

To run the alternative version:
```sh
python bot1.py
```

## APIs Used
- **CoinGecko API**: Fetches token price and market cap.
- **GeckoTerminal API**: Retrieves historical and real-time price trends.
- **Telegram API**: Sends alerts for important token updates.

## File Breakdown
### `bot.py`
- Main execution file for MavBot.
- Reads token addresses from shard files.
- Fetches data and calculates holders.
- Sends token updates to Telegram.

### `bot1.py`
- Alternative execution file with slight modifications.
- Includes additional logging and debugging features.

### `utils.py`
- Utility functions for API requests and data processing.

### `config.json`
- Stores configuration settings for API calls and token monitoring.

## Logging and Debugging
- Logs are saved in the `logs/` directory.
- Use `--debug` flag for detailed console output.
- Errors are recorded for troubleshooting.

## Future Enhancements
- Implement AI-based trading strategies.
- Add support for more cryptocurrency exchanges.
- Introduce a web dashboard for monitoring.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Contributions are welcome! If you find any issues or have suggestions, feel free to open an issue or a pull request.
