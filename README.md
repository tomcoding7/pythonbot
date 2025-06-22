# Yu-Gi-Oh Card Arbitrage Bot

A Python bot for scraping and analyzing Yu-Gi-Oh card auctions on Buyee.jp. This tool helps identify profitable card trading opportunities by comparing prices across different auction platforms.

## Features

- Automated scraping of Buyee.jp auction listings
- Card condition analysis using AI
- Price comparison with 130point.com
- Multi-language support (Japanese/English)
- Stealth browser automation
- Comprehensive error handling and logging

## Prerequisites

- Python 3.8+
- Chrome browser
- OpenAI API key
- Google Generative AI API key

## Installation

1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
```

## Usage

Run the scraper:
```bash
python buyee_scraper.py
```

The script will:
1. Scrape auction listings from Buyee.jp
2. Analyze card conditions and prices
3. Save results to `scraped_results` directory
4. Generate detailed logs in `scraper.log`

## Configuration

The scraper can be configured through command line arguments:

```bash
python buyee_scraper.py --help
```

Available options:
- `--output-dir`: Directory to save results (default: scraped_results)
- `--max-pages`: Maximum number of pages to scrape per search (default: 5)
- `--headless`: Run Chrome in headless mode (default: True)

## Project Structure

```
.
├── src/                      # Source code directory
│   ├── buyee_scraper.py     # Main scraper implementation
│   ├── scraper_utils.py     # Utility classes and functions
│   ├── card_analyzer.py     # Card analysis logic
│   ├── image_analyzer.py    # Image processing
│   ├── rank_analyzer.py     # Card ranking analysis
│   └── search_terms.py      # Search term definitions
├── requirements.txt          # Project dependencies
├── .env                      # Environment variables
├── README.md                 # Project documentation
├── buyee_listings.csv        # Scraped data
├── buyee_listings.json       # Scraped data
├── scraper.log               # Log file
├── scraped_results/          # Directory for scraped data
└── venv/                     # Python virtual environment
```

## Error Handling

The bot includes comprehensive error handling:
- Network timeouts and retries
- Bot detection bypass
- Resource cleanup
- Detailed logging
- Debug information saving

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to the OpenAI and Google AI teams for their APIs
- Special thanks to the Selenium and BeautifulSoup communities
- Inspired by various open-source scraping projects
