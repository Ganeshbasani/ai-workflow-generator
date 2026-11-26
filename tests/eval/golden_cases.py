"""25 golden cases covering every domain the application supports."""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_BY_DOMAIN = {
    "business": "Business Organizations",
    "education": "Educational Institutes",
    "real_estate": "Real Estate",
    "software": "Software Industries",
    "hospital": "Hospitals",
    "infrastructure": "Software Industries",
}

# Two deliberate first-attempt schema failures exercise the repair loop.
REPAIR_CASE_IDS = frozenset({"g04", "g17"})


@dataclass(frozen=True)
class GoldenCase:
    id: str
    description: str
    category: str
    expected_domain: str
    min_steps: int


_RAW: tuple[tuple[str, str, int], ...] = (
    ("Customer registers and places an order", "business", 2),
    ("Process the payment and generate an invoice", "business", 2),
    ("Onboard a new client and process the purchase order", "business", 2),
    ("Arrange shipment and delivery for the order", "business", 1),
    ("Handle the failed payment for a customer order", "business", 1),
    ("Update customer records and save them to the database", "business", 2),
    ("A student applies for admission", "education", 1),
    ("Verify student documents during admission", "education", 2),
    ("Enroll the student into a course", "education", 1),
    ("Schedule the examination and publish the results", "education", 2),
    ("The teacher assigns subjects to the students", "education", 1),
    ("Book a doctor appointment for the patient", "hospital", 1),
    ("Patient check-in and vitals recording", "hospital", 1),
    ("Perform a medical diagnosis and issue a prescription", "hospital", 2),
    ("Process discharge and final billing for the patient", "hospital", 1),
    ("Schedule an appointment and prescribe medicine", "hospital", 2),
    ("Create a property listing for the rental", "real_estate", 1),
    ("Schedule a property viewing for the buyer", "real_estate", 1),
    ("Draft the lease agreement for the tenant", "real_estate", 1),
    ("Log a maintenance request for the property", "real_estate", 1),
    ("Analyze the project requirements and design the system", "software", 2),
    ("Develop the feature and perform QA testing", "software", 2),
    ("Deploy the release to production", "software", 1),
    ("Authenticate the user login on the server", "infrastructure", 1),
    ("Monitor server health and perform an automated backup", "infrastructure", 2),
)

GOLDEN_CASES: tuple[GoldenCase, ...] = tuple(
    GoldenCase(
        id=f"g{index:02d}",
        description=description,
        category=CATEGORY_BY_DOMAIN[domain],
        expected_domain=domain,
        min_steps=min_steps,
    )
    for index, (description, domain, min_steps) in enumerate(_RAW, start=1)
)
