"""The curated shortlist of benchmark companies, per sector, plus their retrieval phrasing.

Two kinds of data, and the split matters:

  * `SECTOR_LEADER_CANDIDATES` -- which companies are credible comparators for a given sector.
    Curated deliberately rather than discovered at runtime, so a benchmark cannot silently drift
    to whatever a search engine surfaced that day.
  * `COMMON_CAPABILITY_RETRIEVAL_PHRASES` -- how to *search* for evidence about a capability.
    "feedback collection" is useless as a query; the expanded phrase describes the practice in the
    words a real article would use, which is what makes the search return anything relevant.

This is reference data, not logic. Adding a sector means adding entries here, with no code change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeaderCandidate:
    key: str
    company_name: str
    domain: str
    search_context: str = ""
    segment: str = ""
    region: str = ""


COMMON_CAPABILITY_RETRIEVAL_PHRASES: dict[str, str] = {
    "use of insights": "turning customer feedback into prioritized actions through root-cause review, owner assignment, and regular follow-up",
    "acting on pain points": "resolving customer pain points through issue ownership, root-cause tracking, prioritization, and closure discipline",
    "feedback collection": "capturing customer feedback through listening channels, surveys, complaint capture, and regular review routines",
    "decision-making": "using customer evidence in decision forums, prioritization reviews, and action planning",
    "cx metrics": "tracking customer experience through dashboards, review cycles, owner linkage, and action-focused metrics",
    "journey visibility": "managing customer journeys through journey mapping, ownership, review cadence, and journey-level metrics",
    "cross-channel consistency": "improving cross-channel customer experience through handoff rules, shared knowledge, and customer context alignment",
    "governance": "managing customer experience through executive sponsorship, cross-functional review forums, and action tracking",
    "cx ownership": "managing customer experience through executive sponsorship, cross-functional review forums, and action tracking",
    "customer-centric culture": "reinforcing customer-focused behaviors through leadership rituals, coaching, recognition, and frontline empowerment",
}


SECTOR_CAPABILITY_RETRIEVAL_PHRASE_OVERRIDES: dict[str, dict[str, str]] = {}


def get_capability_retrieval_phrases(sector_key: str) -> dict[str, str]:
    phrases = dict(COMMON_CAPABILITY_RETRIEVAL_PHRASES)
    phrases.update(SECTOR_CAPABILITY_RETRIEVAL_PHRASE_OVERRIDES.get(sector_key, {}))
    return phrases


TELECOM_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "verizon",
        "Verizon",
        "verizon.com",
        "telecommunications company known for AI-powered customer experience, personalized support, and service innovation",
        region="US",
    ),
    LeaderCandidate(
        "vodafone",
        "Vodafone",
        "vodafone.com",
        "global telecommunications company known for customer experience transformation, digital service, and connected customer journeys",
        region="Global",
    ),
    LeaderCandidate(
        "telstra",
        "Telstra",
        "telstra.com.au",
        "telecommunications company known for customer advocacy, service improvement, and digital experience programs",
        region="APAC",
    ),
    LeaderCandidate(
        "orange",
        "Orange",
        "orange.com",
        "global telecommunications company known for digital customer relations, AI-enabled service, and customer feedback programs",
        region="Global",
    ),
    LeaderCandidate(
        "t-mobile",
        "T-Mobile",
        "t-mobile.com",
        "telecommunications company known for unconventional customer service models, digital support, and customer care innovation",
        region="US",
    ),
    LeaderCandidate(
        "swisscom",
        "Swisscom",
        "swisscom.ch",
        "telecommunications company known for high-quality service operations, digital customer experience, and customer care modernization",
        region="Europe",
    ),
)


BANKING_INSURANCE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "jpmorgan-chase",
        "JPMorgan Chase",
        "jpmorganchase.com",
        "largest investment bank and financial services company, known for digital banking innovation, customer data intelligence, and API-driven service platforms",
        segment="banking",
        region="US",
    ),
    LeaderCandidate(
        "dbs-bank",
        "DBS Bank",
        "dbs.com.sg",
        "Asia's leading digital bank, known for digital-first banking, AI-powered customer experience, and agile service delivery",
        segment="banking",
        region="APAC",
    ),
    LeaderCandidate(
        "ing",
        "ING",
        "ing.com",
        "European digital banking leader, known for digital banking transformation, automated service delivery, and customer-centric innovation",
        segment="banking",
        region="Europe",
    ),
    LeaderCandidate(
        "ally-financial",
        "Ally Financial",
        "ally.com",
        "US digital-first bank, known for omnichannel banking, customer service excellence, and digital-first operations",
        segment="banking",
        region="US",
    ),
    LeaderCandidate(
        "progressive",
        "Progressive",
        "progressive.com",
        "US insurance leader, known for data-driven insurance, digital policy management, and customer self-service innovation",
        segment="insurance",
        region="US",
    ),
    LeaderCandidate(
        "axa",
        "AXA",
        "axa.com",
        "global insurance giant, known for integrated risk management, digital customer platforms, and operational efficiency",
        segment="insurance",
        region="Global",
    ),
    LeaderCandidate(
        "geico",
        "GEICO",
        "geico.com",
        "US insurance leader, known for customer service excellence, digital quote-to-bind automation, and agent-customer operations",
        segment="insurance",
        region="US",
    ),
    LeaderCandidate(
        "lemonade",
        "Lemonade",
        "lemonade.com",
        "InsurTech leader, known for AI-powered claims processing, digital-first insurance, and real-time customer feedback loops",
        segment="insurance",
        region="US",
    ),
)


RETAIL_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "target",
        "Target",
        "target.com",
        "US retail leader, known for omnichannel store-to-digital integration, guest experience innovation, and seamless service operations",
        region="US",
    ),
    LeaderCandidate(
        "best-buy",
        "Best Buy",
        "bestbuy.com",
        "US electronics retailer, known for employee-driven customer service, omnichannel support, and customer experience recovery",
        region="US",
    ),
    LeaderCandidate(
        "costco",
        "Costco",
        "costco.com",
        "membership-based retailer, known for customer loyalty programs, operational efficiency, and service consistency",
        region="US",
    ),
    LeaderCandidate(
        "uniqlo",
        "Uniqlo",
        "uniqlo.com",
        "Asian retail leader, known for product-service integration, customer feedback-driven design, and omnichannel store experience",
        region="APAC",
    ),
    LeaderCandidate(
        "sephora",
        "Sephora",
        "sephora.com",
        "luxury beauty retailer, known for personalized beauty retail experience, digital engagement, and omnichannel integration",
        region="Global",
    ),
    LeaderCandidate(
        "hm",
        "H&M",
        "hm.com",
        "fashion retailer, known for digital fashion retail, omnichannel customer experience, and sustainability-integrated operations",
        region="Global",
    ),
)


ECOMMERCE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "amazon",
        "Amazon",
        "amazon.com",
        "e-commerce and cloud computing giant, known for customer obsession, omnichannel fulfillment, data-driven personalization, and logistics-driven service",
        region="Global",
    ),
    LeaderCandidate(
        "shopify",
        "Shopify",
        "shopify.com",
        "e-commerce platform provider, known for merchant success, API-driven platform design, and customer-centric product development",
        region="Global",
    ),

    LeaderCandidate(
        "ebay",
        "eBay",
        "ebay.com",
        "online marketplace leader, known for seller-buyer feedback systems, marketplace trust mechanisms, and auction-driven customer experience",
        region="Global",
    ),
    LeaderCandidate(
        "etsy",
        "Etsy",
        "etsy.com",
        "digital marketplace for handmade goods, known for seller community building, customer experience personalization, and marketplace trust",
        region="Global",
    ),
    LeaderCandidate(
        "rakuten",
        "Rakuten",
        "rakuten.com",
        "Japanese e-commerce and digital services giant, known for loyalty programs, omnichannel integration, and customer data utilization",
        region="APAC",
    ),
)


BANKING_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "jpmorgan-chase",
        "JPMorgan Chase",
        "jpmorganchase.com",
        "largest investment bank and financial services company, known for digital banking innovation, customer data intelligence, and API-driven service platforms",
        region="US",
    ),
    LeaderCandidate(
        "dbs-bank",
        "DBS Bank",
        "dbs.com.sg",
        "Asia's leading digital bank, known for digital-first banking, AI-powered customer experience, and agile service delivery",
        region="APAC",
    ),
    LeaderCandidate(
        "goldman-sachs",
        "Goldman Sachs",
        "goldmansachs.com",
        "global investment banking leader, known for wealth management innovation, digital advisory services, and client experience transformation",
        region="Global",
    ),
    LeaderCandidate(
        "hsbc",
        "HSBC",
        "hsbc.com",
        "global banking leader, known for international customer operations, digital transformation, and emerging market customer experience",
        region="Global",
    ),
    LeaderCandidate(
        "square",
        "Square",
        "square.com",
        "fintech platform, known for seller-first design, omnichannel payment integration, and business-focused customer experience",
        region="US",
    ),
)


INSURANCE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "progressive",
        "Progressive",
        "progressive.com",
        "US insurance leader, known for data-driven insurance, digital policy management, and customer self-service innovation",
        region="US",
    ),
    LeaderCandidate(
        "axa",
        "AXA",
        "axa.com",
        "global insurance giant, known for integrated risk management, digital customer platforms, and operational efficiency",
        region="Global",
    ),
    LeaderCandidate(
        "zurich",
        "Zurich",
        "zurich.com",
        "global insurance provider, known for risk management solutions, digital customer platforms, and operational excellence",
        region="Global",
    ),
    LeaderCandidate(
        "munich-re",
        "Munich Re",
        "munichre.com",
        "reinsurance and insurance leader, known for risk analytics, data-driven underwriting, and digital innovation",
        region="Global",
    ),
    LeaderCandidate(
        "lemonade",
        "Lemonade",
        "lemonade.com",
        "InsurTech leader, known for AI-powered claims processing, digital-first insurance, and real-time customer feedback loops",
        region="US",
    ),
)


HEALTHCARE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "unitedhealth",
        "UnitedHealth",
        "unitedhealthgroup.com",
        "largest US health insurer and provider, known for integrated health services, digital member engagement, and health data analytics",
        region="US",
    ),
    LeaderCandidate(
        "mayo-clinic",
        "Mayo Clinic",
        "mayoclinic.org",
        "leading healthcare provider, known for patient experience excellence, integrated care delivery, and digital health innovation",
        region="US",
    ),
    LeaderCandidate(
        "kaiser-permanente",
        "Kaiser Permanente",
        "kaiserpermanente.org",
        "largest US HMO, known for integrated care delivery, digital patient engagement, and health data platforms",
        region="US",
    ),
    LeaderCandidate(
        "cleveland-clinic",
        "Cleveland Clinic",
        "clevelandclinic.org",
        "top patient experience leader, known for patient-centered operations, clinical care excellence, and service innovation",
        region="US",
    ),
    LeaderCandidate(
        "teladoc-health",
        "Teladoc Health",
        "teladoc.com",
        "virtual care innovation leader, known for virtual care operations, patient engagement technology, and remote service delivery",
        region="US",
    ),
    LeaderCandidate(
        "humana",
        "Humana",
        "humana.com",
        "large health insurer, known for personalized health coverage, digital member engagement, and health outcomes integration",
        region="US",
    ),
)


HOSPITALITY_TRAVEL_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "marriott",
        "Marriott",
        "marriott.com",
        "largest hospitality company, known for guest experience personalization, loyalty-program integration, and omnichannel service orchestration",
        segment="hospitality",
        region="Global",
    ),
    LeaderCandidate(
        "four-seasons",
        "Four Seasons",
        "fourseasons.com",
        "luxury hospitality leader, known for luxury service excellence, employee empowerment, and personalized guest experience",
        segment="hospitality",
        region="Global",
    ),
    LeaderCandidate(
        "hilton",
        "Hilton",
        "hilton.com",
        "large hotel operator, known for hotel portfolio optimization, guest experience consistency, and digital check-in innovation",
        segment="hospitality",
        region="Global",
    ),
    LeaderCandidate(
        "airbnb",
        "Airbnb",
        "airbnb.com",
        "sharing economy hospitality leader, known for community trust, host and guest feedback loops, and marketplace service operations",
        segment="hospitality",
        region="Global",
    ),
    LeaderCandidate(
        "booking-com",
        "Booking.com",
        "booking.com",
        "online travel agency leader, known for customer-centric marketplace operations, booking experience optimization, and guest feedback integration",
        segment="travel",
        region="Global",
    ),
    LeaderCandidate(
        "expedia",
        "Expedia",
        "expedia.com",
        "travel technology company, known for omnichannel travel booking, customer experience personalization, and loyalty program integration",
        segment="travel",
        region="Global",
    ),
    LeaderCandidate(
        "united-airlines",
        "United Airlines",
        "united.com",
        "major airline carrier, known for customer service innovation, digital-first operations, and loyalty program excellence",
        segment="travel",
        region="US",
    ),
    LeaderCandidate(
        "kayak",
        "Kayak",
        "kayak.com",
        "travel search and booking aggregator, known for customer-centric search experience, price comparison transparency, and user feedback-driven development",
        segment="travel",
        region="Global",
    ),
)


TRAVEL_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "booking-com",
        "Booking.com",
        "booking.com",
        "online travel agency leader, known for customer-centric marketplace operations, booking experience optimization, and guest feedback integration",
        region="Global",
    ),
    LeaderCandidate(
        "expedia",
        "Expedia",
        "expedia.com",
        "travel technology company, known for omnichannel travel booking, customer experience personalization, and loyalty program integration",
        region="Global",
    ),
    LeaderCandidate(
        "united-airlines",
        "United Airlines",
        "united.com",
        "major airline carrier, known for customer service innovation, digital-first operations, and loyalty program excellence",
        region="US",
    ),
    LeaderCandidate(
        "kayak",
        "Kayak",
        "kayak.com",
        "travel search and booking aggregator, known for customer-centric search experience, price comparison transparency, and user feedback-driven development",
        region="Global",
    ),
    LeaderCandidate(
        "marriott-bonvoy",
        "Marriott Bonvoy",
        "marriott.com",
        "global loyalty program, known for loyalty program personalization, rewards integration across hospitality brands, and member experience optimization",
        region="Global",
    ),
)


TECHNOLOGY_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "salesforce",
        "Salesforce",
        "salesforce.com",
        "largest CRM platform, known for customer success platforms, AI-driven customer intelligence, and community-driven feedback loops",
        region="Global",
    ),
    LeaderCandidate(
        "hubspot",
        "HubSpot",
        "hubspot.com",
        "marketing and CRM platform, known for freemium customer acquisition, product-led growth, and customer feedback-driven development",
        region="Global",
    ),
    LeaderCandidate(
        "slack",
        "Slack",
        "slack.com",
        "workplace collaboration platform, known for user-centric product design, community engagement, and customer-informed product strategy",
        region="Global",
    ),
    LeaderCandidate(
        "atlassian",
        "Atlassian",
        "atlassian.com",
        "developer-focused software company, known for developer-focused product design, community-driven support, and customer feedback integration",
        region="Global",
    ),
    LeaderCandidate(
        "datadog",
        "Datadog",
        "datadoghq.com",
        "cloud monitoring and analytics platform, known for customer success platforms, AI-powered insights, and developer-community engagement",
        region="Global",
    ),
    LeaderCandidate(
        "stripe",
        "Stripe",
        "stripe.com",
        "payment and financial infrastructure provider, known for developer experience excellence, transparent API design, and customer-centric platform engineering",
        region="Global",
    ),
)


PUBLIC_SERVICE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "uk-gds",
        "UK Government Digital Service",
        "digital.gov.uk",
        "government digital services unit, known for citizen-focused digital service design, agile government transformation, and accessibility-first platforms",
        region="UK",
    ),
    LeaderCandidate(
        "us-social-security-administration",
        "US Social Security Administration",
        "ssa.gov",
        "major US government agency, known for citizen service operations, digital modernization, and large-scale operational efficiency",
        region="US",
    ),
    LeaderCandidate(
        "smart-nation-singapore",
        "Singapore Government",
        "gov.sg",
        "Asia's leader in digital government services, known for integrated citizen platforms, data-driven service delivery, and public sector innovation",
        region="APAC",
    ),
    LeaderCandidate(
        "service-nsw",
        "Service NSW",
        "service.nsw.gov.au",
        "state digital services hub, known for omnichannel citizen service delivery, integrated government platforms, and service redesign",
        region="APAC",
    ),
    LeaderCandidate(
        "canada-digital-services",
        "Canada Digital Services",
        "canada.ca",
        "government digital services, known for citizen-centric service design, digital modernization, and accessibility standards",
        region="North America",
    ),
    LeaderCandidate(
        "estonia-egovernance",
        "Estonia E-Governance",
        "estonia.ee",
        "world leader in digital government, known for digital-first service delivery, e-residency programs, and data-driven citizen operations",
        region="Europe",
    ),
)


PUBLIC_SECTOR_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = PUBLIC_SERVICE_LEADER_CANDIDATES


RETAIL_ECOMMERCE_LEADER_CANDIDATES: tuple[LeaderCandidate, ...] = (
    LeaderCandidate(
        "amazon",
        "Amazon",
        "amazon.com",
        "e-commerce and retail giant, known for customer obsession, omnichannel fulfillment, data-driven personalization, and service operations at scale",
        segment="ecommerce",
        region="Global",
    ),
    LeaderCandidate(
        "target",
        "Target",
        "target.com",
        "US retail leader, known for omnichannel store-to-digital integration, guest experience innovation, and seamless service operations",
        segment="retail",
        region="US",
    ),
    LeaderCandidate(
        "shopify",
        "Shopify",
        "shopify.com",
        "commerce platform provider, known for merchant success, API-driven platform design, and customer-centric product development",
        segment="ecommerce",
        region="Global",
    ),
    LeaderCandidate(
        "best-buy",
        "Best Buy",
        "bestbuy.com",
        "US electronics retailer, known for employee-driven customer service, omnichannel support, and customer experience recovery",
        segment="retail",
        region="US",
    ),
    LeaderCandidate(
        "costco",
        "Costco",
        "costco.com",
        "membership-based retailer, known for customer loyalty programs, operational efficiency, and service consistency",
        segment="retail",
        region="US",
    ),
    LeaderCandidate(
        "ebay",
        "eBay",
        "ebay.com",
        "online marketplace leader, known for seller-buyer feedback systems, marketplace trust mechanisms, and auction-driven customer experience",
        segment="ecommerce",
        region="Global",
    ),
)


SECTOR_LEADER_CANDIDATES: dict[str, tuple[LeaderCandidate, ...]] = {
    "telecom": TELECOM_LEADER_CANDIDATES,
    "banking_insurance": BANKING_INSURANCE_LEADER_CANDIDATES,
    "retail": RETAIL_LEADER_CANDIDATES,
    "ecommerce": ECOMMERCE_LEADER_CANDIDATES,
    "banking": BANKING_LEADER_CANDIDATES,
    "insurance": INSURANCE_LEADER_CANDIDATES,
    "healthcare": HEALTHCARE_LEADER_CANDIDATES,
    "hospitality_travel": HOSPITALITY_TRAVEL_LEADER_CANDIDATES,
    "travel": TRAVEL_LEADER_CANDIDATES,
    "technology": TECHNOLOGY_LEADER_CANDIDATES,
    "public_services": PUBLIC_SERVICE_LEADER_CANDIDATES,
    "public_sector": PUBLIC_SECTOR_LEADER_CANDIDATES,
    "retail_ecommerce": RETAIL_ECOMMERCE_LEADER_CANDIDATES,
}


__all__ = [
    "LeaderCandidate",
    "COMMON_CAPABILITY_RETRIEVAL_PHRASES",
    "SECTOR_CAPABILITY_RETRIEVAL_PHRASE_OVERRIDES",
    "get_capability_retrieval_phrases",
    "TELECOM_LEADER_CANDIDATES",
    "BANKING_INSURANCE_LEADER_CANDIDATES",
    "RETAIL_LEADER_CANDIDATES",
    "ECOMMERCE_LEADER_CANDIDATES",
    "BANKING_LEADER_CANDIDATES",
    "INSURANCE_LEADER_CANDIDATES",
    "HEALTHCARE_LEADER_CANDIDATES",
    "HOSPITALITY_TRAVEL_LEADER_CANDIDATES",
    "TRAVEL_LEADER_CANDIDATES",
    "TECHNOLOGY_LEADER_CANDIDATES",
    "PUBLIC_SERVICE_LEADER_CANDIDATES",
    "PUBLIC_SECTOR_LEADER_CANDIDATES",
    "RETAIL_ECOMMERCE_LEADER_CANDIDATES",
    "SECTOR_LEADER_CANDIDATES",
]
