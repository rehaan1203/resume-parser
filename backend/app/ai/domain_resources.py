"""Domain-specific resource library with fallback."""
from typing import Dict, List, Optional
from app.models.domain_models import Domain, DomainResources, DomainResource

class DomainResourceLibrary:
    """Comprehensive resource library for all domains with fallback."""

    # Hardcoded fallback resources for all domains
    FALLBACK_RESOURCES = DomainResources(
        free_courses=[
            DomainResource(
                name="Introduction to the Domain",
                platform="Coursera",
                url="https://www.coursera.org",
                type="free_course",
                description="Fundamental course covering key domain concepts"
            ),
            DomainResource(
                name="Domain Fundamentals",
                platform="edX",
                url="https://www.edx.org",
                type="free_course",
                description="Comprehensive introduction to the domain"
            )
        ],
        paid_courses=[
            DomainResource(
                name="Advanced Domain Certification",
                platform="Udemy",
                url="https://www.udemy.com",
                type="paid_course",
                description="Deep dive into domain-specific knowledge"
            )
        ],
        youtube_channels=[
            DomainResource(
                name="Domain Learning Channel",
                platform="YouTube",
                url="https://www.youtube.com",
                type="youtube_channel",
                description="Educational videos covering domain topics"
            )
        ],
        certifications=[
            DomainResource(
                name="Professional Domain Certification",
                platform="Certification Board",
                url="https://www.example.com",
                type="certification",
                description="Industry-recognized domain certification"
            )
        ]
    )

    # Specific resources for each domain
    RESOURCES = {
        Domain.LEGAL: DomainResources(
            free_courses=[
                DomainResource(
                    name="Introduction to Contract Law",
                    platform="Coursera",
                    url="https://www.coursera.org/learn/contract-law",
                    type="free_course",
                    description="Learn the fundamentals of contract law"
                ),
                DomainResource(
                    name="Legal Research 101",
                    platform="YouTube",
                    url="https://www.youtube.com/results?search_query=legal+research+tutorial",
                    type="youtube_channel",
                    description="Tutorials on legal research methods"
                ),
                DomainResource(
                    name="Understanding Corporate Law",
                    platform="edX",
                    url="https://www.edx.org/learn/corporate-law",
                    type="free_course",
                    description="Corporate law fundamentals"
                )
            ],
            paid_courses=[
                DomainResource(
                    name="Corporate Law Certification",
                    platform="Udemy",
                    url="https://www.udemy.com/topic/corporate-law/",
                    type="paid_course",
                    description="Comprehensive corporate law course"
                ),
                DomainResource(
                    name="Legal Tech and Innovation",
                    platform="Coursera",
                    url="https://www.coursera.org/learn/legal-tech",
                    type="paid_course",
                    description="Learn about technology in the legal industry"
                )
            ],
            youtube_channels=[
                DomainResource(
                    name="Legal Eagle",
                    platform="YouTube",
                    url="https://www.youtube.com/c/LegalEagle",
                    type="youtube_channel",
                    description="Legal education and commentary"
                ),
                DomainResource(
                    name="Law & Technology",
                    platform="YouTube",
                    url="https://www.youtube.com/results?search_query=law+and+technology",
                    type="youtube_channel",
                    description="The intersection of law and technology"
                )
            ],
            certifications=[
                DomainResource(
                    name="Certified Compliance Professional",
                    platform="SCCE",
                    url="https://www.corporatecompliance.org/",
                    type="certification",
                    description="Compliance certification"
                ),
                DomainResource(
                    name="Legal Tech Certification",
                    platform="LegalTech",
                    url="https://www.legaltech.com/certification",
                    type="certification",
                    description="Legal technology certification"
                )
            ]
        ),
        # Add more domains as needed...
    }

    def get_resources(self, domain: Domain) -> DomainResources:
        """Get resources for a given domain with fallback."""
        return self.RESOURCES.get(domain, self.FALLBACK_RESOURCES)
