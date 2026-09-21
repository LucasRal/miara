"""Jeu de données de démo pour `FakeCRM` (tests et mode démo, ADR-008).

Un compte fil rouge (TechStart) richement peuplé, plus un second compte pour
vérifier l'isolation des recherches. Dates calées sur « aujourd'hui » pour que
les fenêtres d'activités (30 / 90 jours) soient testables.
"""

from datetime import date, timedelta

from app.sales.crm.fake import FakeCRM


async def seed_demo(crm: FakeCRM) -> dict[str, str]:
    """Peuple `crm` et renvoie les ids utiles aux tests."""
    today = date.today()
    recent = (today - timedelta(days=10)).isoformat()
    old = (today - timedelta(days=200)).isoformat()

    techstart = await crm.create(
        "Account",
        {
            "Name": "TechStart SAS",
            "Industry": "Logiciel",
            "Phone": "+33 1 23 45 67 89",
            "Website": "techstart.example",
        },
    )
    globex = await crm.create(
        "Account", {"Name": "Globex Corp", "Industry": "Industrie", "Phone": "+33 4 00 00 00 00"}
    )

    razafy = await crm.create(
        "Contact",
        {
            "Name": "Hanta Razafy",
            "Email": "h.razafy@techstart.example",
            "Phone": "+33 6 11 22 33 44",
            "Title": "Directrice des achats",
            "AccountId": techstart,
        },
    )
    await crm.create(
        "Contact",
        {
            "Name": "Paul Martin",
            "Email": "p.martin@globex.example",
            "Title": "Responsable IT",
            "AccountId": globex,
        },
    )

    opp_open = await crm.create(
        "Opportunity",
        {
            "Name": "TechStart - Licences 2026",
            "StageName": "Proposition",
            "Amount": 48000,
            "CloseDate": (today + timedelta(days=30)).isoformat(),
            "AccountId": techstart,
            "IsClosed": False,
        },
    )
    await crm.create(
        "Opportunity",
        {
            "Name": "TechStart - Pilote (clôturée)",
            "StageName": "Closed Won",
            "Amount": 12000,
            "CloseDate": old,
            "AccountId": techstart,
            "IsClosed": True,
        },
    )

    case_open = await crm.create(
        "Case",
        {
            "CaseNumber": "00001042",
            "Subject": "Souci de connexion SSO",
            "Status": "En cours",
            "Priority": "Haute",
            "AccountId": techstart,
            "IsClosed": False,
        },
    )
    await crm.create(
        "Case",
        {
            "CaseNumber": "00001001",
            "Subject": "Question facturation (résolue)",
            "Status": "Closed",
            "AccountId": techstart,
            "IsClosed": True,
        },
    )

    await crm.create(
        "Task",
        {
            "Subject": "Appel de suivi",
            "ActivityDate": recent,
            "Status": "Terminé",
            "WhatId": techstart,
        },
    )
    await crm.create(
        "Task",
        {
            "Subject": "Relance ancienne",
            "ActivityDate": old,
            "Status": "Terminé",
            "WhatId": techstart,
        },
    )
    await crm.create(
        "Event",
        {"Subject": "Réunion de cadrage", "ActivityDate": recent, "WhatId": techstart},
    )

    # Étapes d'opportunité de l'org (pour la validation des écritures d'étape).
    for label, active in [
        ("Prospection", True),
        ("Proposition", True),
        ("Négociation", True),
        ("Closed Won", True),
        ("Closed Lost", True),
        ("Ancienne étape", False),
    ]:
        await crm.create("OpportunityStage", {"MasterLabel": label, "IsActive": active})

    return {
        "techstart": techstart,
        "globex": globex,
        "razafy": razafy,
        "opp_open": opp_open,
        "case_open": case_open,
    }
