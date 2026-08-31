"""Fetch and extract job descriptions from URLs."""
import httpx
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict

class URLFetcher:
    """Fetch JD from job board URLs."""

    # Known job boards
    JOB_BOARDS = {
        "linkedin.com": "linkedin",
        "indeed.com": "indeed",
        "glassdoor.com": "glassdoor",
        "monster.com": "monster",
        "dice.com": "dice"
    }

    async def fetch(self, url: str) -> Optional[Dict[str, any]]:
        """Fetch and extract JD from URL."""
        try:
            board = self._identify_board(url)
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, 'html.parser')
                # Remove unwanted elements
                for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()

                # Extract based on board
                if board == "linkedin":
                    text = self._extract_linkedin(soup)
                elif board == "indeed":
                    text = self._extract_indeed(soup)
                else:
                    text = self._extract_generic(soup)

                # Extract title
                title = self._extract_title(soup, url)

                return {"text": text, "title": title, "url": url, "source": board}
        except Exception as e:
            return None

    def _identify_board(self, url: str) -> Optional[str]:
        for domain, board in self.JOB_BOARDS.items():
            if domain in url.lower():
                return board
        return None

    def _extract_linkedin(self, soup: BeautifulSoup) -> str:
        selectors = ['.description__text', '.show-more-less-html__markup', '[data-test-id="job-details"]']
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator='\n', strip=True)
        return soup.get_text(separator='\n', strip=True)[:10000]

    def _extract_indeed(self, soup: BeautifulSoup) -> str:
        selectors = ['#jobDescriptionText', '.job-description', '[data-testid="jobDescriptionText"]']
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                return content.get_text(separator='\n', strip=True)
        return soup.get_text(separator='\n', strip=True)[:10000]

    def _extract_generic(self, soup: BeautifulSoup) -> str:
        # Generic extraction for unknown boards
        all_text = soup.get_text(separator='\n', strip=True)
        keywords = ['job description', 'responsibilities', 'qualifications']
        lines = all_text.split('\n')
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in keywords):
                start = max(0, i - 5)
                end = min(len(lines), i + 30)
                return '\n'.join(lines[start:end])
        return all_text[:10000]

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        selectors = ['h1', '.job-title', '.title', '[data-test-id="job-title"]']
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) < 200:
                    return title
        return url.split('/')[-1].replace('-', ' ')[:100]
