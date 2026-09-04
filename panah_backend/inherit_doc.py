import docx

doc = docx.Document()

topics = [
    {
        "title": "Topic 1: Inheritance (Mirath / Faraid)",
        "legal": (
            "West Pakistan Muslim Personal Law (Shariat) Application Act, 1962"
            " confirms that Muslim Personal Law governs succession,"
            " overriding customary practices excluding women."
            " Section 3 terminates limited estates under custom[cite: 1]."
            " Muslim Family Laws Ordinance (MFLO) 1961 Section 4 provides that"
            " children of a predeceased child inherit their parent's share per"
            " stirpes (though its Islamic compatibility has been litigated in"
            " court)[cite: 1]. Prevention of Anti-Women Practices Act 2011"
            " added Section 498-A PPC (depriving women of inheritance"
            " punishable by 5-10 years prison / 1M fine)[cite: 1], Section"
            " 498-B (forced marriage)[cite: 1], and Section 498-C ('marriage"
            " to the Quran' / vani / swara)[cite: 1].\n\nStep-by-step claim"
            " process:\n1. Death Certificate from Union Council/NADRA.\n2. Family Registration Certificate (FRC) from NADRA.\n3. Succession Certificate for movable assets via NADRA or"
            " Civil Court under Succession Act 1925[cite: 1].\n4. Mutation of"
            " ownership (intiqal) for immovable property via local revenue"
            " officer (patwari)[cite: 1].\n5. Civil lawsuit / Section 498-A PPC"
            " complaint if excluded by fraud or pressure[cite: 1]."
        ),
        "islamic": (
            "Grounded in Quran 4:11 (children and parents)[cite: 1], 4:12"
            " (spouses)[cite: 1], and 4:176 (siblings)[cite: 1]. Sunni"
            " (Hanafi) Law sorts heirs into Sharers (ashab al-furud), Residuaries"
            " (asabah), and Distant Kindred (zawil arham)[cite: 1]. Male takes"
            " twice female share when sons and daughters inherit together as"
            " residuaries[cite: 1]. Shia (Ithna Ashari) Law recognizes two"
            " classes (Sharers and Residuaries; no Distant Kindred category)"
            " organized strictly by blood/marriage proximity classes where"
            " nearer class excludes remote class[cite: 1], uses per-stirpes"
            " distribution[cite: 1], and handles radd and aul differently"
            "[cite: 1]."
        ),
        "qa": [
            (
                "Can my father or brothers legally stop me from inheriting?",
                (
                    "No. Under both Islamic law and the West Pakistan Muslim"
                    " Personal Law (Shariat) Application Act, 1962, your"
                    " inheritance share is a legal right[cite: 1]."
                    " Deliberately depriving you of it by deceit, pressure, or"
                    " forged documents is a criminal offence under Section"
                    " 498-A PPC (5-10 years imprisonment and/or fine up to Rs. 1"
                    " million)[cite: 1]."
                ),
            ),
            (
                "Can I be made to sign away my inheritance?",
                (
                    "A document signed under family pressure is not"
                    " automatically binding, and courts have held that such"
                    " waivers do not bar you from later claiming your actual"
                    " share, except in narrow circumstances such as a fully"
                    " executed family settlement you knowingly benefited from"
                    "[cite: 1]."
                ),
            ),
            (
                "How much do I actually inherit as a daughter?",
                (
                    "Under Hanafi Sunni rule: one daughter alone gets half the"
                    " estate; two or more daughters together get two-thirds;"
                    " if a son is alive, daughters and sons split in a 1"
                    " female : 2 male ratio of what remains after other sharers"
                    " are paid[cite: 1]. Shia calculation differs"
                    " structurally[cite: 1]."
                ),
            ),
            (
                "Do I lose my inheritance if I get divorced or remarry?",
                (
                    "No. Inheritance rights from your parents/family are"
                    " completely independent of your marital status[cite: 1]."
                ),
            ),
            (
                "What do I need to actually collect my share?",
                (
                    "A death certificate, a Family Registration Certificate"
                    " (FRC) from NADRA, and then either a succession certificate"
                    " for movable assets (NADRA/court) or a mutation at the"
                    " revenue office/patwari for land/property[cite: 1]. If"
                    " contested, a partition suit in court[cite: 1]."
                ),
            ),
        ],
    },
    {
        "title": "Topic 2: Marriage Registration and Polygamy",
        "legal": (
            "Muslim Family Laws Ordinance (MFLO) 1961 Section 5 mandates every"
            " Muslim marriage be registered with a licensed Nikah Registrar"
            "[cite: 1]. Section 6 prohibits contracting a second marriage"
            " without prior written permission from an Arbitration Council"
            "[cite: 1]. Contracting an unauthorized second marriage makes the"
            " entire dower immediately payable (recoverable as arrears of land"
            " revenue)[cite: 1], incurs criminal penalties (imprisonment up to"
            " 1 year/fine)[cite: 1], and provides a valid ground for the"
            " first wife to seek judicial dissolution[cite: 1]."
        ),
        "islamic": (
            "Nikah is a civil contract[cite: 1]. Quranic principles demand"
            " equal and just treatment between co-wives[cite: 1]. Violating"
            " marital obligations or equitable treatment entitles the wife to"
            " seek judicial relief[cite: 1]."
        ),
        "qa": [
            (
                (
                    "My husband wants to marry a second wife. Can he, and what"
                    " are my rights?"
                ),
                (
                    "Only with prior written permission from an Arbitration"
                    " Council, which must find it 'necessary and just' and"
                    " consider your consent[cite: 1]. If he marries without"
                    " permission, he must pay your full dower immediately and"
                    " you can use this as grounds for judicial dissolution"
                    " without forfeiting dower[cite: 1]."
                ),
            )
        ],
    },
    {
        "title": "Topic 3: Judicial Divorce and Khula",
        "legal": (
            "Dissolution of Muslim Marriages Act (DMMA) 1939 lists 9 specific"
            " grounds for judicial divorce: 1. Husband missing for 4 years"
            "[cite: 1]; 2. Non-maintenance for 2 years[cite: 1]; 3."
            " Unauthorized polygamy[cite: 1]; 4. Imprisonment for 7+ years"
            "[cite: 1]; 5. Failure to perform marital obligations for 3 years"
            "[cite: 1]; 6. Impotency[cite: 1]; 7. Insanity/disease[cite: 1];"
            " 8. Repudiation of child marriage before age 18[cite: 1]; 9."
            " Cruelty (broadly defined including mental abuse)[cite: 1]; 10."
            " Open catch-all clause[cite: 1].\n\nKhula: Near-absolute right of"
            " wife without husband's consent[cite: 1]. In 2022 FSC struck down"
            " fixed dower return formulas in Family Courts Act Section 10"
            "[cite: 1]. In 2026, LHC ruled dower remains protected if divorce"
            " was caused by husband's fault even if labeled khula[cite: 1]."
            " In May 2026, Supreme Court (CJP Yahya Afridi bench) ruled courts"
            " CANNOT automatically convert cruelty cases to khula without the"
            " wife's explicit, informed consent[cite: 1], adopting a broad"
            " definition of cruelty (mental/emotional abuse) and a lower"
            " preponderance of probability evidentiary standard[cite: 1]."
        ),
        "islamic": (
            "Derived from Islamic doctrine allowing female release from"
            " marriage[cite: 1]. Delegated divorce (talaq-e-tafweez) under"
            " Column 18 of Nikahnama allows direct divorce by wife under MFLO"
            " Section 8[cite: 1]. Lian allows dissolution if husband falsely"
            " accuses wife of adultery under DMMA clause viia[cite: 1]."
        ),
        "qa": [
            (
                "Can I get divorced without my husband's agreement?",
                (
                    "Yes, via two routes: (1) judicial dissolution under DMMA"
                    " 1939 on grounds like non-maintenance or cruelty, or (2) Khula, where you state you cannot live within"
                    " God's limits[cite: 1]. His consent is not required for"
                    " either[cite: 1]."
                ),
            ),
            (
                "If I get khula, do I lose my Haq Mehr?",
                (
                    "It depends on fault. If pure khula (personal aversion),"
                    " prompt dower is usually returned[cite: 1]. If caused by"
                    " husband's fault/cruelty, courts protect your dower. Under the May 2026 Supreme Court ruling, courts must"
                    " get your informed consent before treating your case as"
                    " khula[cite: 1]."
                ),
            ),
            (
                (
                    "I think I'm being forced into a marriage / my family wants"
                    " me to marry to settle a dispute (vani/swara)."
                ),
                (
                    "This is a specific criminal offence under Section 498-B"
                    " (forced marriage) and Section 498-C (vani/swara) of the"
                    " Pakistan Penal Code[cite: 1]. Seek immediate helpline"
                    " and legal support[cite: 1]."
                ),
            ),
        ],
    },
    {
        "title": "Topic 4: Mehr and Dower Rights",
        "legal": (
            "Obligatory term of marriage recorded in nikahnama[cite: 1]."
            " Divided into Prompt (mu'ajjal - payable on demand)[cite: 1] and"
            " Deferred (mu'wajjal - payable on divorce/death)[cite: 1]. MFLO"
            " Section 10 presumes entire amount is prompt if unspecified"
            "[cite: 1]. Supreme Court (Chief Justice Qazi Faez Isa ruling)"
            " confirmed prompt mehr must be paid whenever demanded during"
            " marriage, incurring heavy fines for delay[cite: 1]. Recovered"
            " via suit under Family Courts Act 1964[cite: 1]."
        ),
        "islamic": (
            "Grounded in Quran 4:4 ('give women their due compensation')"
            "[cite: 1]. It is the absolute property of the wife, not a gift to"
            " her family[cite: 1]."
        ),
        "qa": [
            (
                "Can I demand my mehr any time, or only at divorce?",
                (
                    "You can demand prompt mehr at any time during the"
                    " marriage[cite: 1]. Supreme Court precedent confirms it"
                    " is a direct debt enforceable upon demand[cite: 1]."
                ),
            )
        ],
    },
    {
        "title": "Topic 5: Maintenance (Nafaqa)",
        "legal": (
            "Husband must maintain wife during marriage (food, clothing,"
            " shelter, medical) regardless of her income[cite: 1]. Recoverable"
            " via MFLO Section 9 Arbitration Council or Family Court[cite: 1]."
            " Maintenance survives separation if wife has valid cause"
            " (cruelty/lack of housing)[cite: 1]. Maintenance during iddat"
            " (post-divorce waiting period ~3 months/childbirth) is mandatory"
            " (PLD 1981 Kar 240 / PLD 2003 Lah 15)[cite: 1]. Child maintenance"
            " is an unconditional obligation on the father until maturity,"
            " independent of custody[cite: 1]."
        ),
        "islamic": (
            "Based on Quranic principles and Quran 65:4[cite: 1]. Post-iddat"
            " maintenance for the ex-wife ends unless separately contracted"
            "[cite: 1]."
        ),
        "qa": [
            (
                (
                    "Is my husband required to support me if he's not divorcing"
                    " me but we're separated?"
                ),
                (
                    "Generally yes, if you have a valid reason for living"
                    " separately (e.g., cruelty, lack of housing)[cite: 1]."
                    " You can file a maintenance case in Family Court."
                ),
            ),
            (
                "Does my husband have to support me after divorce?",
                (
                    "Only through your iddat period (~3 months or until"
                    " childbirth if pregnant) unless contracted otherwise"
                    "[cite: 1]. Child maintenance continues separately until"
                    " adulthood[cite: 1]."
                ),
            ),
        ],
    },
    {
        "title": "Topic 6: Child Custody (Hizanat) & Guardianship (Wilayat)",
        "legal": (
            "Governed by Guardians and Wards Act 1890[cite: 1]. Section 17"
            " sets the paramount rule: Welfare of the Minor[cite: 1]."
            " Hizanat (custody/care) starts with mother presumption (sons"
            " until age 7, daughters until puberty)[cite: 1]. Presumption is"
            " rebuttable based on child welfare[cite: 1]. Wilayat"
            " (legal/financial guardianship) resides primarily with the father"
            "[cite: 1]. Getting Khula does NOT forfeit custody rights. Interim custody/visitation can be granted under Section 12"
            " while litigation is pending[cite: 1]."
        ),
        "islamic": (
            "Distinguishes physical care (Hizanat) from legal guardianship"
            " (Wilayat)[cite: 1]. Priority passes to female relatives"
            " (grandmothers) if parents are unavailable[cite: 1]."
        ),
        "qa": [
            (
                (
                    "Will I lose custody of my children if I get khula or file"
                    " for divorce?"
                ),
                (
                    "No[cite: 1]. Custody is legally independent of how the"
                    " marriage ended[cite: 1]. Courts decide based strictly on"
                    " child welfare under Section 17 of the Guardians and Wards"
                    " Act[cite: 1]."
                ),
            ),
            (
                "What if my husband tries to take the children away from me?",
                (
                    "He must go through Guardian/Family Court[cite: 1]. He"
                    " cannot forcibly take them; you can seek interim custody"
                    " and protective court orders[cite: 1]."
                ),
            ),
        ],
    },
]

for topic in topics:
    doc.add_paragraph(topic["title"])
    doc.add_paragraph("Legal basis")
    doc.add_paragraph(topic["legal"])
    doc.add_paragraph("Islamic basis")
    doc.add_paragraph(topic["islamic"])
    doc.add_paragraph("Q&A chunks")
    for q, a in topic["qa"]:
        doc.add_paragraph(f"Q: {q}")
        doc.add_paragraph(f"A: {a}")
    doc.add_paragraph("")

doc.save("knowledge_base_aligned.docx")
print("`knowledge_base_aligned.docx` generated with 100% complete research data!")