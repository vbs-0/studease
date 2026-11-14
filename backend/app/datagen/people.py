"""Synthetic students. Names are random combinations; emails use the reserved example.edu domain, so no real
person is described (S-21). Distributions are reasoned, not fitted to any real institution."""
import random
from datetime import date, timedelta
from decimal import Decimal

from app import ids
from app.datagen.rand import weighted

FIRST = ["Aarav", "Aditi", "Aisha", "Akash", "Ananya", "Arjun", "Bhavya", "Chaitanya", "Deepak", "Divya", "Esha",
         "Farhan", "Gauri", "Harsh", "Isha", "Jatin", "Kavya", "Kunal", "Lakshmi", "Manav", "Meera", "Naveen",
         "Neha", "Omkar", "Pooja", "Prakash", "Rahul", "Riya", "Rohan", "Sana", "Sanjay", "Shreya", "Siddharth",
         "Sneha", "Tanvi", "Uday", "Vaishnavi", "Varun", "Yash", "Zoya", "Liam", "Olivia", "Noah", "Emma", "Lucas",
         "Mia", "Ethan", "Amara", "Kofi", "Mei"]
LAST = ["Agarwal", "Bhat", "Chandra", "Desai", "Dutta", "Fernandes", "Gupta", "Iyer", "Jain", "Kapoor", "Khan",
        "Kulkarni", "Mehta", "Menon", "Mishra", "Nair", "Pandey", "Patel", "Pillai", "Rao", "Reddy", "Saxena",
        "Shah", "Sharma", "Singh", "Sinha", "Subramanian", "Thakur", "Trivedi", "Verma", "Yadav", "Chen", "Smith",
        "Okafor", "Silva", "Kim", "Nguyen", "Garcia", "Muller", "Rossi"]
MEAN_GPA, SD_GPA = 7.7, 1.1


def students(r: random.Random, n: int, programs: list[dict], late_admits: int) -> tuple[list[dict], set[int]]:
    """`n` students; `late_admits` of them are admitted in spring and so skip the SPRING term."""
    weights = [1 / (i + 1) ** 0.6 for i in range(len(programs))]
    r.shuffle(weights)                                   # which programs are big is itself random
    late = set(r.sample(range(1, n + 1), late_admits))
    rows = []
    for no in range(1, n + 1):
        gpa = Decimal(f"{min(10.0, max(4.0, r.gauss(MEAN_GPA, SD_GPA))):.2f}")
        intl = r.random() < 0.08
        u = r.random()
        waiver = "STAFF_WARD" if u < 0.015 else "SIBLING" if u < 0.055 else "HARDSHIP" if u < 0.085 else None
        first, last = r.choice(FIRST), r.choice(LAST)
        admitted = (date(2026, 4, 25) + timedelta(days=r.randint(0, 15)) if no in late
                    else date(2025, 6, 1) + timedelta(days=r.randint(0, 90)))
        rows.append({
            "student_id": ids.student_id(no),
            "program_id": weighted(r, [p["program_id"] for p in programs], weights),
            "full_name": f"{first} {last}", "email": f"{first}.{last}.{no:06d}@example.edu".lower(),
            "residency": "INTERNATIONAL" if intl else "DOMESTIC", "gpa": gpa,
            "income_band": weighted(r, ["LOW", "MID", "HIGH", "AFFLUENT"], [30, 43, 22, 5]),
            "sports_quota": r.random() < 0.04, "hostel_resident": r.random() < (0.45 if intl else 0.28),
            "waiver_type": waiver, "admitted_on": admitted})
    return rows, late
