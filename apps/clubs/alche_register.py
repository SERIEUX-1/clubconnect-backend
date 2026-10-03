"""Official ALCHE Clubs and Societies Database + Club ExCo. (workbook)."""

ALCHE_STUDENT_DOMAINS = [
    "alustudent.com",
    "si.alueducation.com",
]

ALCHE_STAFF_DOMAINS = [
    "alueducation.com",
]

ALCHE_CLUBS = [
    {
        "name": "ACF (ALCHE Christian Fellowship) Society",
        "category": "Faith",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Christian fellowship society for students at ALCHE.",
        "constitution": "ACF constitution",
        "president": {"name": "Orphelie Perrine", "email": "m.perrine@alustudent.com"},
        "vice_president": {"name": "Olivier Bigirimana", "email": "o.bigiriman@alustudent.com"},
        "treasurer": {"name": "Olivier Ishimwe", "email": ""},
    },
    {
        "name": "The Alchemists' Times",
        "category": "Media",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Campus newspaper and newsletter society.",
        "constitution": "Newspaper and Newsletter Club Constitution",
        "president": {"name": "Tejisvani Pudaruth", "email": "tpudaruth@si.alueducation.com"},
        "notes": "ExCo roles not explicitly stated.",
    },
    {
        "name": "Writing club - Beyond the Page",
        "category": "Academic",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Writing club for student authors and editors.",
        "constitution": "Writing Club Constitution",
        "president": {"name": "Tejisvani Pudaruth", "email": "tpudaruth@si.alueducation.com"},
        "vice_president": {"name": "Hanif Olayiwola", "email": ""},
        "treasurer": {"name": "Elera-Obari Josiah-Chu", "email": "e.josiah-ch@alustudent.com"},
    },
    {
        "name": "Rwandan Students Society",
        "category": "Cultural",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Society for Rwandan students at ALCHE.",
        "constitution": "Constitution of the Rwandan Student Society (RSS) at ALCHE",
        "president": {"name": "Moulaika Mugeni", "email": "m.mugeni@alustudent.com"},
        "vice_president": {"name": "Tako Nellyvine", "email": "n.mizero@alustudent.com"},
        "treasurer": {"name": "Olivier Bigirimana", "email": "o.bigiriman@alustudent.com"},
        "officers": [
            {"title": "Co-Vice President", "name": "Acher Mpakaniye", "email": "a.mpakaniye@alustudent.com"},
        ],
    },
    {
        "name": "ALCHE BlockChain Club",
        "category": "Technology",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Student society for blockchain learning and projects.",
        "constitution": "ALCHE Blockchain Club Constitution",
        "president": {"name": "Hanif Olayiwola", "email": ""},
        "vice_president": {"name": "Moses Uzowuru", "email": "c.uzowuru@alustudent.com"},
        "treasurer": {"name": "Immaculata Emmanuel", "email": ""},
    },
    {
        "name": "Adventure club",
        "category": "Recreation",
        "cycle": "August 2025",
        "status": "dormant",
        "description": "Dissolved after operational challenges; the club later requested dissolution.",
        "constitution": "Constitution of Adventure Club",
        "president": {"name": "Elera Obari", "email": ""},
        "notes": "The Club was dissolved due to operational challenges. While the issue was initially identified by the committee, the club later formally requested dissolution during efforts to revive its activities.",
    },
    {
        "name": "Steppers Club",
        "category": "Arts & Culture",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Dance society (Steppers Dance Club).",
        "constitution": "Steppers Dance Club Constitution",
        "president": {"name": "Immaculata Effiong", "email": ""},
        "notes": "Registration form access still needed by the committee.",
    },
    {
        "name": "Muslims@ALCHE",
        "category": "Faith",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Muslim student society at ALCHE.",
        "constitution": "Muslims@ALCHE Constitution",
        "president": {"name": "Sheriff Sumaila", "email": "s.sumaila@alustudent.com"},
        "vice_president": {"name": "Yahya Bouhaik", "email": "y.bouhaik@alustudent.com"},
        "treasurer": {"name": "Farhaan Khuroolah", "email": "f.khuroolah@alustudent.com"},
    },
    {
        "name": "French Club",
        "category": "Academic",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "French language and culture society.",
        "constitution": "French Club Constitution",
        "president": {"name": "Amahn Heuvel", "email": ""},
        "vice_president": {"name": "Janique Maduray", "email": "j.maduray@alustudent.com"},
        "treasurer": {"name": "Lisette Mukiza", "email": "l.mukiza@alustudent.com"},
    },
    {
        "name": "Karma Football Club",
        "category": "Recreation",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Student football club (Karma FC).",
        "constitution": "KARMA FC Constitution",
        "president": {"name": "Laizer Olais Julius", "email": "j.laizer@alustudent.com"},
        "vice_president": {"name": "Sampson Foli", "email": "s.foli@alustudent.com"},
        "treasurer": {"name": "Khuroolah Farhaan", "email": "f.khuroolah@alustudent.com"},
    },
    {
        "name": "Alchemist Creators",
        "category": "Arts & Culture",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "Student creators' society for visual and media work.",
        "constitution": "Constitution of Alchemist Creators",
        "president": {"name": "Immaculata Effiong", "email": ""},
        "vice_president": {"name": "Yahya Bouhaik", "email": "h.mohammed@alustudent.com"},
        "treasurer": {"name": "Hanif Olayiwola", "email": ""},
    },
    {
        "name": "ALCHEPELLA",
        "category": "Arts & Culture",
        "cycle": "August 2025",
        "status": "recognized",
        "description": "A cappella and vocal performance society.",
        "constitution": "Alchepella Constitution",
        "president": {"name": "Louisa Chisom", "email": "l.chisom@alustudent.com"},
        "vice_president": {"name": "Baraza Brian", "email": "b.mwololo@alustudent.com"},
        "treasurer": {"name": "Moulaika Mugeni", "email": "m.mugeni@alustudent.com"},
    },
    {
        "name": "Young African Luminaries at ALCHE",
        "category": "Leadership",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Leadership society at ALCHE. Previously the Pan African Society.",
        "constitution": "YAL Manual Handbook",
        "president": {"name": "Belly Hakizimana", "email": "b.hakiziman2@alustudent.com"},
        "vice_president": {"name": "Ishimwe Olivier", "email": "o.ishimwe2@alustudent.com"},
        "treasurer": {"name": "Tejasvini Pudaruth", "email": "t.pudaruth@alustudent.com"},
        "notes": "Previously the Pan African Society.",
    },
    {
        "name": "Robotics club",
        "category": "Technology",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Student robotics society at ALCHE.",
        "constitution": "ALCHE Robotics Club",
        "president": {"name": "Stephy Rukundo", "email": ""},
        "vice_president": {"name": "Chukwudumebi Emmanuella Ukogu", "email": "c.ukogu@alustudent.com"},
        "treasurer": {"name": "Leatitia Mizero", "email": "laetitiamizero0@gmail.com"},
    },
    {
        "name": "ALCHE Wall Street Investment Club",
        "category": "Academic",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Investment and markets society (AWSIC).",
        "constitution": "ALCHE Wall Street Investment Society Constitution",
        "president": {"name": "Ayomide Ajayi", "email": "a.ajayi@alustudent.com"},
        "vice_president": {"name": "Tooshar Kumar Sauntoo", "email": "t.sauntoo@alustudent.com"},
        "treasurer": {"name": "Halimatu Sadia Mohammed", "email": "h.mohammed@alustudent.com"},
    },
    {
        "name": "Zero to checkmate",
        "category": "Recreation",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Chess club (Zero to Checkmate).",
        "constitution": "ALCHE Zero to Checkmate Chess Club Constitution",
        "president": {"name": "Oogoti Faith Kerubo", "email": "f.ogoti@alustudent.com"},
        "vice_president": {"name": "Nelson Fodjo", "email": "n.fodjokamd@alustudent.com"},
        "treasurer": {"name": "Chinelo Adaugo Nnamdi", "email": "c.nnamdika@alustudent.com"},
    },
    {
        "name": "Alchemists Gardening Club",
        "category": "Sustainability",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Campus gardening society.",
        "constitution": "Alchemist Gardening Club constitution",
        "president": {"name": "Ewaoluwa Oladipo", "email": ""},
        "vice_president": {"name": "Kelechi Oparaji", "email": "k.oparaji@alustudent.com"},
        "treasurer": {"name": "Shuqroh Adekunle", "email": "s.adekunle@alustudent.com"},
    },
    {
        "name": "ShieldXHack@ALCHE",
        "category": "Technology",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Cybersecurity society at ALCHE.",
        "constitution": "Constitution of ShieldXHack @ ALCHE",
        "president": {"name": "Chrys Gnagne", "email": ""},
        "vice_president": {"name": "Abigail Inyang", "email": "a.inyang@alustudent.com"},
        "treasurer": {"name": "Abduljabar Abdulkadir", "email": "a.abdulkadi@alustudent.com"},
        "notes": "Documents listed two secretaries rather than a treasurer; one was recorded as treasurer.",
    },
    {
        "name": "ALCHE Badminton Club",
        "category": "Recreation",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Badminton society.",
        "constitution": "ALCHE Badminton Club Constitution",
        "president": {"name": "Fortunate Ansong", "email": "f.ansong@alustudent.com"},
        "vice_president": {"name": "Goodness Muoka", "email": "g.muoka@alustudent.com"},
        "treasurer": {"name": "Osman Inusah", "email": "o.inusah@alustudent.com"},
    },
    {
        "name": "TichTechy Hub",
        "category": "Technology",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Student technology hub.",
        "constitution": "TictechyHub Club Constitution",
        "president": {"name": "Titilayo Daniyan", "email": ""},
        "vice_president": {"name": "Ademo Oluwawapelumi", "email": "o.ademo@alustudent.com"},
        "treasurer": {"name": "Afuwape Opeyemi", "email": "o.afuwape@alustudent.com"},
    },
    {
        "name": "Art club",
        "category": "Arts & Culture",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Visual arts society (The Blank Canvas).",
        "constitution": "The Blank Canvas Arts Club Constitution",
        "president": {"name": "Onyinyechi Richard", "email": ""},
        "vice_president": {"name": "Leslie Mugiraneza", "email": "l.mugiranez@alustudent.com"},
        "treasurer": {"name": "Aishat Adedire", "email": "a.adedire@alustudent.com"},
    },
    {
        "name": "Ghanaian society",
        "category": "Cultural",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Ghanaian student society at ALCHE.",
        "constitution": "Constitution Ghanaian Society",
        "president": {"name": "Korkor Ndede Kojo", "email": "k.ndedekojo@alustudent.com"},
        "vice_president": {"name": "Samuel Anagbah", "email": "s.anagbah@alustudent.com"},
        "treasurer": {"name": "Nadia Akua Nsiah Odame", "email": "n.odame@alustudent.com"},
    },
    {
        "name": "Ubuntu ballers",
        "category": "Recreation",
        "cycle": "March 2026",
        "status": "recognized",
        "description": "Student basketball society (Ubuntu Ballers).",
        "constitution": "Ubuntu Ballers Constitution",
        "president": {"name": "James Sanga", "email": "j.sanga@alustudent.com"},
        "vice_president": {"name": "Andrea Memba", "email": "a.memba@alustudent.com"},
        "treasurer": {"name": "Edith Otieno", "email": "e.otieno1@alustudent.com"},
    },
]

LICENSED_STUDENT_DOMAINS = frozenset(ALCHE_STUDENT_DOMAINS)


def is_licensed_student_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    return email.rsplit("@", 1)[1].lower().strip() in LICENSED_STUDENT_DOMAINS


def split_person_name(full_name: str):
    parts = (full_name or "").strip().split()
    if not parts:
        return "Student", "Leader"
    if len(parts) == 1:
        return parts[0], "Leader"
    return parts[0], " ".join(parts[1:])


def club_officer_rows(row: dict):
    officers = []
    for title, key in (
        ("President", "president"),
        ("Vice President", "vice_president"),
        ("Treasurer", "treasurer"),
    ):
        person = row.get(key)
        if person and (person.get("name") or person.get("email")):
            officers.append(
                {
                    "title": title,
                    "name": (person.get("name") or "").strip(),
                    "email": (person.get("email") or "").strip(),
                }
            )
    for extra in row.get("officers") or []:
        officers.append(
            {
                "title": extra.get("title") or "Officer",
                "name": (extra.get("name") or "").strip(),
                "email": (extra.get("email") or "").strip(),
            }
        )
    return officers
