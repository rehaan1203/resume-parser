"""Smart job description extraction from URLs."""
import httpx
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import re
from app.utils.logger import logger

class JDExtractor:
    """Extract job description from various job board URLs."""
    
    # Known job board patterns
    JOB_BOARDS = {
        "linkedin.com": "linkedin",
        "indeed.com": "indeed",
        "glassdoor.com": "glassdoor",
        "monster.com": "monster",
        "ziprecruiter.com": "ziprecruiter",
        "dice.com": "dice",
        "careerbuilder.com": "careerbuilder",
        "remote.co": "remote_co",
        "weworkremotely.com": "weworkremotely"
    }
    
    async def extract(self, url: str) -> Optional[Dict[str, any]]:
        """Extract job description from URL."""
        try:
            # Identify job board
            board = self._identify_board(url)
            logger.info(f"Extracting JD from {board or 'unknown'} board: {url}")
            
            # Fetch HTML
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch URL: {response.status_code}")
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove unwanted elements
                for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                # Extract title
                title = self._extract_title(soup, url)
                
                # Extract based on board
                if board == "linkedin":
                    result = self._extract_linkedin(soup)
                elif board == "indeed":
                    result = self._extract_indeed(soup)
                elif board == "glassdoor":
                    result = self._extract_glassdoor(soup)
                else:
                    result = self._extract_generic(soup)
                
                result["title"] = title
                result["url"] = url
                result["board"] = board
                
                return result
                    
        except Exception as e:
            logger.error(f"JD extraction failed: {e}")
            return None
    
    def _identify_board(self, url: str) -> Optional[str]:
        """Identify job board from URL."""
        for domain, board in self.JOB_BOARDS.items():
            if domain in url.lower():
                return board
        return None
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """Extract job title from page."""
        # Try common selectors
        selectors = [
            'h1',
            '.job-title',
            '.title',
            '[data-test-id="job-title"]',
            '.position-title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) < 200:
                    return title
        
        # Fallback: use URL path
        path = url.split('/')[-1].replace('-', ' ').replace('_', ' ')
        return path[:100] if path else "Unknown Position"
    
    def _extract_linkedin(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Extract from LinkedIn job page."""
        # Try multiple selectors for robustness
        selectors = [
            '.description__text',
            '.show-more-less-html__markup',
            '[data-test-id="job-details"]',
            '.job-description',
            '.description'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                text = content.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    return {"text": text, "source": "linkedin"}
        
        # Fallback: look for job description containers
        for element in soup.find_all(['div', 'section']):
            classes = ' '.join(element.get('class', []))
            if 'description' in classes.lower() or 'details' in classes.lower():
                text = element.get_text(separator='\n', strip=True)
                if len(text) > 500:
                    return {"text": text, "source": "linkedin"}
        
        # Ultimate fallback
        text = soup.get_text(separator='\n', strip=True)
        # Try to extract job description section
        keywords = ['job description', 'about the job', 'role overview']
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in keywords):
                start = max(0, i - 2)
                end = min(len(lines), i + 50)
                context = '\n'.join(lines[start:end])
                return {"text": context, "source": "linkedin"}
        
        return {"text": text[:10000], "source": "linkedin"}
    
    def _extract_indeed(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Extract from Indeed job page."""
        selectors = [
            '#jobDescriptionText',
            '.job-description',
            '[data-testid="jobDescriptionText"]',
            '.jobsearch-JobComponent-description'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                text = content.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    return {"text": text, "source": "indeed"}
        
        return {"text": soup.get_text(separator='\n', strip=True)[:10000], "source": "indeed"}
    
    def _extract_glassdoor(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Extract from Glassdoor job page."""
        selectors = [
            '.jobDescriptionContent',
            '[data-test="jobDescription"]',
            '.desc',
            '.job-desc'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                text = content.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    return {"text": text, "source": "glassdoor"}
        
        return {"text": soup.get_text(separator='\n', strip=True)[:10000], "source": "glassdoor"}
    
    def _extract_generic(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Generic extraction for unknown job boards."""
        # Look for common job description containers
        common_patterns = [
            r'job[-_]?description',
            r'role[-_]?description',
            r'position[-_]?description',
            r'opportunity[-_]?description',
            r'about[-_]?the[-_]?role',
            r'responsibilities',
            r'qualifications'
        ]
        
        for element in soup.find_all(['div', 'section', 'article']):
            classes = ' '.join(element.get('class', []))
            id_attr = element.get('id', '')
            combined = (classes + ' ' + id_attr).lower()
            
            for pattern in common_patterns:
                if re.search(pattern, combined):
                    text = element.get_text(separator='\n', strip=True)
                    if len(text) > 500:
                        return {"text": text, "source": "generic"}
        
        # Fallback: get all text and try to find JD section
        all_text = soup.get_text(separator='\n', strip=True)
        
        # Try to find JD by keywords
        keywords = ['job description', 'role overview', 'responsibilities', 'qualifications', 'requirements']
        lines = all_text.split('\n')
        
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in keywords):
                # Take context around the keyword
                start = max(0, i - 5)
                end = min(len(lines), i + 30)
                context = '\n'.join(lines[start:end])
                if len(context) > 300:
                    return {"text": context, "source": "generic"}
        
        return {"text": all_text[:10000], "source": "generic"}
    
    async def extract_multiple(self, urls: List[str]) -> List[Dict[str, any]]:
        """Extract from multiple URLs."""
        results = []
        for url in urls:
            result = await self.extract(url)
            if result:
                results.append(result)
        return results
