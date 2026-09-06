/**
 * Panah — i18n.js
 * Shared language state and translations for Urdu, English, and Roman Urdu.
 *
 * Usage:
 *   - Mark static elements with data-i18n="path.to.key"
 *   - Mark attributes with data-i18n-attr="placeholder:chat.placeholder|aria-label:chat.sendLabel"
 *   - Mark innerHTML (for <strong> etc.) with data-i18n-html="trust.note"
 *   - Call PanahI18n.applyLanguage() on page load
 */

const I18N = {
  ur: {
    nav: {
      home: "ہوم",
      about: "ہمارے بارے میں",
      contact: "رابطہ",
      privacy: "رازداری اور حفاظت",
      login: "لاگ ان",
      chat: "بات چیت",
      menuToggle: "مینو کھولیں یا بند کریں",
    },
    hero: {
      title: "جہاں سوالات بھی محفوظ ہیں",
      subtitle:
        "مہر، نفقہ، اور دھوکے سے بچاؤ کے سوالات کا سیدھا جواب، اپنی زبان میں، بغیر کسی راۓ زنی کے۔",
      cta: "پناہ سے پوچھیں",
    },
    topics: {
      title: "کس چیز میں مدد چاہیے؟",
      mehr: {
        title: "مہر",
        desc: "شادی کے وقت آپ کا حق۔ جانیں کب، کیسے، اور کس شکل میں یہ آپ کو ملتا ہے۔",
      },
      nafaqa: {
        title: "نفقہ",
        desc: "اپنے گزارے کے لیے خرچہ۔ سمجھیں اپنا حق اور کہاں سے مدد مل سکتی ہے۔",
      },
      zakat: {
        title: "زکوٰۃ",
        desc: "اسلامی زکوٰۃ کے فرائض اور حقوق کو سمجھیں، حساب سے لے کر مستحقین تک۔",
      },
      scam: {
        title: "دھوکے سے بچاؤ",
        desc: "جھوٹی کالز، انعام کے پیغامات، اور فراڈ اسکیموں سے پہچانیں اور اپنے آپ کو بچائیں۔",
      },
    },
    steps: {
      title: "یہ کیسے کام کرتی ہے؟",
      step1: {
        title: "اپنا سوال پوچھیں",
        body: "لکھ کر بھیجیں یا مائک دبا کر بولیں، اردو، رومن اردو، یا انگریزی میں۔",
      },
      step2: {
        title: "پناہ سنتی ہے",
        body: "آپ کا سوال سمجھ کر صحیح، بھروسے مند معلومات تلاش کرتی ہے۔",
      },
      step3: {
        title: "سیدھا رہنمائی حاصل کریں",
        body: "آسان الفاظ میں جواب، آواز میں سننے کے لیے بھی، بغیر کسی تکنیکی اصطلاحات کے۔",
      },
    },
    trust: {
      note: "<strong>آپ کی بات نجی ہے۔</strong><br />کوئی راۓ زنی نہیں، کسی کو رپورٹ نہیں، صرف آپ کی مدد کے لیے ایک محفوظ جگہ۔",
    },
    footer: {
      tagline: "پناہ، جہاں سوالات بھی محفوظ ہیں۔",
    },
    entry: {
      langTitle: "اپنی زبان منتخب کریں",
      langSubtitle: "آپ جس زبان میں بات کرنا چاہیں، پناہ اسی میں جواب دے گی۔",
      langSkip: "اردو میں جاری رکھیں",
      entryTitle: "لاگ ان کریں یا مہمان کے طور پر جاری رکھیں",
      entrySubtitle:
        "لاگ ان کرنے سے آپ کی گفتگو محفوظ ہو جائے گی۔ مہمان کے طور پر بھی مکمل رسائی حاصل کر سکتے ہیں۔",
      login: "فون نمبر سے لاگ ان کریں",
      guest: "مہمان کے طور پر جاری رکھیں",
    },
    chat: {
      appName: "پناہ",
      subtitle: "جہاں سوالات بھی محفوظ ہیں",
      placeholder: "اپنا سوال لکھیں یا بولیں...",
      micLabel: "اپنا سوال بولیں",
      sendLabel: "بھیجیں",
      speakerLabel: "آواز",
      suggestedTitle: "مثالی سوالات",
      welcome:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔ آپ کی بات بالکل محفوظ ہے، کچھ بھی save نہیں ہوتا۔",
      welcomeLoggedIn:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔",
      newChat: "نئی گفتگو",
      historyLabel: "پچھلی گفتگو",
      settings: "ترتیبات",
      welcomeUrdu:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔ آپ کی بات بالکل محفوظ ہے، کچھ بھی save نہیں ہوتا۔",
      welcomeUrduLoggedIn:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔",
      welcomeEnglish:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak. Your conversation is completely private, nothing is saved.",
      welcomeEnglishLoggedIn:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak.",
      settingsTitle: "ترتیبات",
      langPrefLabel: "زبان کی ترجیح",
      langUrdu: "اردو",
      langEnglish: "انگریزی",
      voiceOutputLabel: "آواز",
      voiceOutputHint: "یہ ترجیح آپ کے اکاؤنٹ کے لیے محفوظ رہے گی۔",
      voiceOn: "چالو",
      voiceOff: "بند",
      clearHistory: "تمام گفتگو صاف کریں",
      clearHistoryConfirm: "کیا آپ واقعی تمام محفوظ گفتگو صاف کرنا چاہتی ہیں؟ یہ عمل واپس نہیں ہو سکتا۔",
      deleteAccount: "اکاؤنٹ حذف کریں",
      deleteAccountTitle: "اکاؤنٹ حذف کریں؟",
      deleteAccountConfirm: "کیا آپ واقعی اپنا اکاؤنٹ حذف کرنا چاہتی ہیں؟ اس سے آپ کی تمام گفتگو ہمیشہ کے لیے حذف ہو جائے گی اور یہ عمل واپس نہیں ہو سکتا۔",
      deleteAccountCancel: "منسوخ کریں",
      deleteAccountConfirmBtn: "ہاں، اکاؤنٹ حذف کریں",
      deleteAccountError: "معذرت، ابھی آپ کا اکاؤنٹ حذف نہیں ہو سکا۔ براہ کرم دوبارہ کوشش کریں۔",
      deleteChat: "حذف کریں",
      logout: "لاگ آؤٹ",
      emptyHistory: "ابھی تک کوئی گفتگو محفوظ نہیں ہوئی۔",
      chips: [
        { topic: "مہر", text: "مہر کا حق کیا ہے؟" },
        { topic: "نفقہ", text: "میرا شوہر مجھے خرچہ نہیں دیتا، میں کیا کروں؟" },
        { topic: "دھوکا", text: "کسی نے مجھے انعام جیتنے کا پیغام بھیجا ہے، کیا یہ جھوٹ ہے؟" },
      ],
    },
    about: {
      title: "ہمارے بارے میں",
      lead: "پناہ ایک محفوظ جگہ ہے جہاں خواتین اپنے حقوق اور تحفظ کے بارے میں بے جھجھک پوچھ سکتی ہیں۔",
      p1: "ہماری کوشش ہے کہ ہر خاتون، چاہے وہ کسی بھی پس منظر سے ہو، اپنے مالی حقوق، مہر، نفقہ، اور دھوکے سے بچاؤ کے بارے میں آسان، قابل اعتماد معلومات حاصل کر سکے۔",
      p2: "ہمارے جوابات اسلامی اور قانونی معلومات پر مبنی ہیں، لیکن ہم وکیل یا مفتی نہیں ہیں۔ ہماری زبان سادہ، گرم جوش، اور بغیر کسی راۓ زنی کے ہے۔",
      valuesTitle: "ہمارے اصول",
      safety: { title: "محفوظ جگہ", body: "کوئی سوال غلط نہیں۔ آپ کی بات نجی رہتی ہے۔" },
      dignity: { title: "عزت نفس", body: "ہم معلومات دیتے ہیں، الزام نہیں۔" },
      access: { title: "رسائی", body: "اردو، رومن اردو، اور انگریزی میں آواز اور تحریر دونوں۔" },
    },
    contact: {
      title: "رابطہ کریں",
      lead: "ہماری ٹیم آپ کی رائے، سوالات، یا تشویش کا جواب دینے کو تیار ہے۔",
      emailLabel: "ای میل",
      phoneLabel: "فون",
      phone: "+92-300-1234567",
      formName: "آپ کا نام",
      formMessage: "آپ کا پیغام",
      formSubmit: "پیغام بھیجیں",
      note: "ہم 24 سے 48 گھنٹوں کے اندر جواب دینے کی کوشش کرتے ہیں۔",
    },
    privacy: {
      title: "رازداری اور حفاظت",
      lead: "ہم جانتے ہیں کہ آپ جو پوچھتی ہیں ذاتی ہو سکتا ہے۔ اس لیے رازداری ہمارے کام کا حصہ ہے۔",
      section1Title: "کیا ہم آپ کی گفتگو محفوظ رکھتے ہیں؟",
      section1Body:
        "اگر آپ مہمان کے طور پر استعمال کرتی ہیں تو آپ کی گفتگو صرف اسی صفحے پر رہتی ہے، ہم اسے اپنے پاس محفوظ نہیں کرتے۔ لاگ ان کرنے پر تاریخ محفوظ ہو سکتی ہے تاکہ آپ بعد میں دیکھ سکیں۔",
      section2Title: "کیا ہم کسی کو رپورٹ کرتے ہیں؟",
      section2Body:
        "نہیں۔ پناہ ایک غیر جانبدار معلوماتی ذریعہ ہے۔ ہم کسی تیسرے فریق کو آپ کی شناخت یا سوالات نہیں بتاتے۔",
      section3Title: "کیا ایپ مجھے جج کرتی ہے؟",
      section3Body:
        "نہیں۔ ہمارا مقصد صرف مدد کرنا ہے۔ کوئی سوال چھوٹا یا بڑا نہیں۔",
    },
    auth: {
      title: "پناہ میں جاری رکھیں",
      subtitle: "اپنی گفتگو محفوظ کریں اور جہاں سے چھوڑا تھا وہیں سے شروع کریں۔",
      phoneLabel: "موبائل نمبر",
      phonePlaceholder: "3XX XXXXXXX",
      sendCode: "کوڈ بھیجیں",
      otpLabel: "OTP کوڈ",
      otpPlaceholder: "6 عددی کوڈ",
      verify: "تصدیق کریں اور جاری رکھیں",
      changeNumber: "دوسرا نمبر استعمال کریں",
      footnote: "پاس ورڈ کی ضرورت نہیں، صرف آپ کا نمبر اور ایک کوڈ۔",
      error: "کچھ غلط ہو گیا۔ براہ کرم دوبارہ کوشش کریں۔",
    },
  },

  en: {
    nav: {
      home: "Home",
      about: "About",
      contact: "Contact",
      privacy: "Privacy & Safety",
      login: "Log in",
      chat: "Chat",
      menuToggle: "Toggle menu",
    },
    hero: {
      title: "Where even questions are safe",
      subtitle:
        "Clear guidance on Mehr, Nafaqa, and scam awareness, in your own language, with no judgment.",
      cta: "Ask Panah",
    },
    topics: {
      title: "What can we help with?",
      mehr: {
        title: "Mehr",
        desc: "Your right at marriage. Learn when, how, and in what form it is owed to you.",
      },
      nafaqa: {
        title: "Nafaqa",
        desc: "Financial support for your living expenses. Understand your right and where to turn for help.",
      },
      zakat: {
        title: "Zakat",
        desc: "Understand your obligations and rights around Islamic almsgiving, from calculation basics to who qualifies to receive it.",
      },
      scam: {
        title: "Scam Safety",
        desc: "Recognize fake calls, prize messages, and fraud schemes, and protect yourself.",
      },
    },
    steps: {
      title: "How it works",
      step1: {
        title: "Ask your question",
        body: "Type it or tap the mic and speak, in Urdu, Roman Urdu, or English.",
      },
      step2: {
        title: "Panah listens",
        body: "It understands your question and finds reliable, relevant information.",
      },
      step3: {
        title: "Get clear guidance",
        body: "Answers in plain language, with the option to hear them aloud, no technical jargon.",
      },
    },
    trust: {
      note: "<strong>Your conversation is private.</strong><br />No judgment, no reporting, just a safe space built to help you.",
    },
    footer: {
      tagline: "Panah, where even questions are safe.",
    },
    entry: {
      langTitle: "Choose your language",
      langSubtitle: "Panah will reply in the language you feel most comfortable using.",
      langSkip: "Continue in Urdu",
      entryTitle: "Log in or continue as a guest",
      entrySubtitle:
        "Logging in lets you save your chats. You still get full access as a guest.",
      login: "Log in with phone number",
      guest: "Continue as guest",
    },
    chat: {
      appName: "Panah",
      subtitle: "Where even questions are safe",
      placeholder: "Type or speak your question...",
      micLabel: "Speak your question",
      sendLabel: "Send",
      speakerLabel: "Voice",
      suggestedTitle: "Example questions",
      welcome:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak. Your conversation is completely private, nothing is saved.",
      welcomeLoggedIn:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak.",
      newChat: "New chat",
      historyLabel: "Past chats",
      settings: "Settings",
      welcomeUrdu:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔ آپ کی بات بالکل محفوظ ہے، کچھ بھی save نہیں ہوتا۔",
      welcomeUrduLoggedIn:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔",
      welcomeEnglish:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak. Your conversation is completely private, nothing is saved.",
      welcomeEnglishLoggedIn:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak.",
      settingsTitle: "Settings",
      langPrefLabel: "Language preference",
      langUrdu: "Urdu",
      langEnglish: "English",
      voiceOutputLabel: "Voice Output",
      voiceOutputHint: "Remember this choice for your account.",
      voiceOn: "On",
      voiceOff: "Off",
      clearHistory: "Clear all chat history",
      clearHistoryConfirm: "Are you sure you want to clear all saved chats? This cannot be undone.",
      deleteAccount: "Delete Account",
      deleteAccountTitle: "Delete account?",
      deleteAccountConfirm: "Are you sure you want to delete your account? This will permanently delete your chat history and cannot be undone.",
      deleteAccountCancel: "Cancel",
      deleteAccountConfirmBtn: "Confirm Delete",
      deleteAccountError: "Sorry, we couldn't delete your account right now. Please try again.",
      deleteChat: "Delete",
      logout: "Log out",
      emptyHistory: "No chats saved yet.",
      chips: [
        { topic: "Mehr", text: "What is my right to Mehr?" },
        { topic: "Nafaqa", text: "My husband does not give me expenses. What can I do?" },
        { topic: "Scam", text: "Someone sent me a prize message. Is it fake?" },
      ],
    },
    about: {
      title: "About us",
      lead: "Panah is a safe space where women can ask about their rights and protection without hesitation.",
      p1: "We believe every woman, regardless of background, deserves simple, trustworthy information about her financial rights, Mehr, Nafaqa, and scam awareness.",
      p2: "Our answers are grounded in Islamic and legal information, but we are not lawyers or scholars. Our tone is warm, respectful, and free of judgment.",
      valuesTitle: "Our values",
      safety: { title: "Safety", body: "No question is wrong. Your conversation stays private." },
      dignity: { title: "Dignity", body: "We share knowledge, not blame." },
      access: { title: "Access", body: "Voice and text in Urdu, Roman Urdu, and English." },
    },
    contact: {
      title: "Contact us",
      lead: "Our team is ready to respond to your feedback, questions, or concerns.",
      emailLabel: "Email",
      phoneLabel: "Phone",
      phone: "+92-300-1234567",
      formName: "Your name",
      formMessage: "Your message",
      formSubmit: "Send message",
      note: "We try to reply within 24 to 48 hours.",
    },
    privacy: {
      title: "Privacy & Safety",
      lead: "We know what you ask can be personal. That is why privacy is built into everything we do.",
      section1Title: "Do we keep your chats?",
      section1Body:
        "If you use Panah as a guest, your chat stays on this page only, we do not store it. Logging in may save history so you can revisit it later.",
      section2Title: "Do we report you to anyone?",
      section2Body:
        "No. Panah is a neutral information service. We do not share your identity or questions with any third party.",
      section3Title: "Will the app judge me?",
      section3Body:
        "Never. Our only goal is to help. No question is too small or too big.",
    },
    auth: {
      title: "Continue to Panah",
      subtitle: "Save your chats and pick up where you left off.",
      phoneLabel: "Mobile number",
      phonePlaceholder: "3XX XXXXXXX",
      sendCode: "Send code",
      otpLabel: "OTP code",
      otpPlaceholder: "6-digit code",
      verify: "Verify & continue",
      changeNumber: "Use a different number",
      footnote: "No password needed, just your number and a code.",
      error: "Something went wrong. Please try again.",
    },
  },

  roman: {
    nav: {
      home: "Home",
      about: "Hamare baare mein",
      contact: "Rabta",
      privacy: "Privacy aur Hifazat",
      login: "Log in",
      chat: "Baat cheet",
      menuToggle: "Menu kholain ya band karein",
    },
    hero: {
      title: "Jahan sawal bhi mehfooz hain",
      subtitle:
        "Mehr, Nafaqa, aur scam se bachao ke sawaalon ka seedha jawab, apni zubaan mein, bina kisi judgement ke.",
      cta: "Panah se poochein",
    },
    topics: {
      title: "Kis cheez mein madad chahiye?",
      mehr: {
        title: "Mehr",
        desc: "Shadi ke waqt aapka haq. Jaanein kab, kaise, aur kis shakal mein ye aapko milta hai.",
      },
      nafaqa: {
        title: "Nafaqa",
        desc: "Apne guzare ke liye kharcha. Samajhein apna haq aur kahan se madad mil sakti hai.",
      },
      zakat: {
        title: "Zakat",
        desc: "Islamic almsgiving ke faraiz aur huqooq ko samjhein, hisaab se le kar mustahiqeen tak.",
      },
      scam: {
        title: "Scam se bachao",
        desc: "Jhoothi calls, prize messages, aur fraud schemes se pehchaanein aur apne aapko bachayein.",
      },
    },
    steps: {
      title: "Kaise kaam karti hai?",
      step1: {
        title: "Apna sawaal poochhein",
        body: "Likh kar bhejein ya mic dabaa kar bolein, Urdu, Roman Urdu, ya English mein.",
      },
      step2: {
        title: "Panah sunegi",
        body: "Aapka sawaal samajh kar sahi, bharosemand information dhoondegi.",
      },
      step3: {
        title: "Seedha guidance paayein",
        body: "Aasan lafzon mein jawab, awaz mein sunnay ke liye bhi, kisi technical jargon ke baghair.",
      },
    },
    trust: {
      note: "<strong>Aapki baat private hai.</strong><br />Koi judgement nahi, kisi ko report nahi, sirf aapki madad ke liye ek mehfooz jagah.",
    },
    footer: {
      tagline: "Panah, jahan sawal bhi mehfooz hain.",
    },
    entry: {
      langTitle: "Apni zubaan chunein",
      langSubtitle: "Panah ussi zubaan mein jawab degi jis mein aap sahmat hain.",
      langSkip: "Urdu mein jari rakhein",
      entryTitle: "Log in karein ya mehmaan ban kar jari rakhein",
      entrySubtitle:
        "Log in karne se aapki guftagu save ho sakti hai. Mehmaan ke tor par bhi poora access milta hai.",
      login: "Phone number se log in karein",
      guest: "Mehmaan ke tor par jari rakhein",
    },
    chat: {
      appName: "Panah",
      subtitle: "Jahan sawal bhi mehfooz hain",
      placeholder: "Apna sawaal likhein ya bolein...",
      micLabel: "Apna sawaal bolein",
      sendLabel: "Bhejein",
      speakerLabel: "Awaz",
      suggestedTitle: "Misaali sawaal",
      welcome:
        "Assalamu Alaikum! Main Panah hoon, jahan sawal bhi mehfooz hain. Aap mujhse Mehr, Nafaqa, Zakat, virasat ya kisi bhi maali haq ke baare mein poochh sakti hain. Apna sawaal likhein ya mic dabaa kar bolein. Aapki baat bilkul mehfooz hai, kuch bhi save nahi hota.",
      welcomeLoggedIn:
        "Assalamu Alaikum! Main Panah hoon, jahan sawal bhi mehfooz hain. Aap mujhse Mehr, Nafaqa, Zakat, virasat ya kisi bhi maali haq ke baare mein poochh sakti hain. Apna sawaal likhein ya mic dabaa kar bolein.",
      newChat: "Nayi guftagu",
      historyLabel: "Pichli guftagu",
      settings: "Settings",
      welcomeUrdu:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔ آپ کی بات بالکل محفوظ ہے، کچھ بھی save نہیں ہوتا۔",
      welcomeUrduLoggedIn:
        "السلام علیکم! میں پناہ ہوں، جہاں سوالات بھی محفوظ ہیں۔ آپ مجھ سے مہر، نفقہ، زکوٰۃ، وراثت یا کسی بھی مالی حق کے بارے میں پوچھ سکتی ہیں۔ اپنا سوال لکھیں یا مائک دبا کر بولیں۔",
      welcomeEnglish:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak. Your conversation is completely private, nothing is saved.",
      welcomeEnglishLoggedIn:
        "Assalamu Alaikum! I am Panah, where even questions are safe. You can ask me about Mehr, Nafaqa, Zakat, inheritance, or any financial right. Type your question or tap the mic to speak.",
      settingsTitle: "Settings",
      langPrefLabel: "Zubaan ki tarjeeh",
      langUrdu: "Urdu",
      langEnglish: "English",
      voiceOutputLabel: "Awaz",
      voiceOutputHint: "Yeh tarjeeh aap ke account ke liye save rahe gi.",
      voiceOn: "On",
      voiceOff: "Off",
      clearHistory: "Tamam guftagu saaf karein",
      clearHistoryConfirm: "Kya aap waali hain ke tamam saved guftagu saaf ho jaye? Yeh wapas nahi ho sakta.",
      deleteAccount: "Account delete karein",
      deleteAccountTitle: "Account delete karein?",
      deleteAccountConfirm: "Kya aap waali hain ke apna account delete karna chahti hain? Is se aap ki tamam guftagu hamesha ke liye delete ho jayegi aur yeh wapas nahi ho sakta.",
      deleteAccountCancel: "Cancel",
      deleteAccountConfirmBtn: "Haan, account delete karein",
      deleteAccountError: "Maazrat, abhi aap ka account delete nahi ho saka. Barah-e-karam dobara koshish karein.",
      deleteChat: "Delete",
      logout: "Log out",
      emptyHistory: "Abhi tak koi guftagu save nahi hui.",
      chips: [
        { topic: "Mehr", text: "Mera haq mehr kya hai?" },
        { topic: "Nafaqa", text: "Mere shohar mujhe kharcha nahi dete, main kya karun?" },
        { topic: "Scam", text: "Kisi ne mujhe prize jeetne ka message bheja hai, kya yeh jhooth hai?" },
      ],
    },
    about: {
      title: "Hamare baare mein",
      lead: "Panah ek mehfooz jagah hai jahan khawateen apne huqooq aur hifazat ke baare mein be-jhijhak poochh sakti hain.",
      p1: "Hamara maqsad hai ke har khatoon, chahay kisi bhi pas manzar se ho, apne maali huqooq, Mehr, Nafaqa, aur scam se bachao ke baare mein aasaan, bharosemand maloomat hasil kar sake.",
      p2: "Hamare jawabaat Islami aur qanooni maloomat par mabni hain, lekin hum wukala ya mufti nahi hain. Hamari zubaan seedhi, garam-josh, aur bila-judgment hai.",
      valuesTitle: "Hamare usool",
      safety: { title: "Mehfooz jagah", body: "Koi sawaal ghalat nahi. Aapki baat niji rehti hai." },
      dignity: { title: "Izzat", body: "Hum maloomat dete hain, ilzam nahi." },
      access: { title: "Rasai", body: "Urdu, Roman Urdu, aur English mein awaz aur likhai donon." },
    },
    contact: {
      title: "Rabta karein",
      lead: "Hamari team aap ki rae, sawaalat, ya tashweesh ka jawab dene ko tayyar hai.",
      emailLabel: "Email",
      phoneLabel: "Phone",
      phone: "+92-300-1234567",
      formName: "Aap ka naam",
      formMessage: "Aap ka paigham",
      formSubmit: "Paigham bhejein",
      note: "Hum 24 se 48 ghanton ke andar jawab dene ki koshish karte hain.",
    },
    privacy: {
      title: "Privacy aur Hifazat",
      lead: "Hum jaante hain ke aap jo poochhti hain zaati ho sakta hai. Is liye privacy hamare kaam ka hissa hai.",
      section1Title: "Kya hum aapki guftagu save karte hain?",
      section1Body:
        "Agar aap mehmaan ke tor par use karti hain to aapki guftagu sirf isi safhe par rehti hai, hum isse apne paas save nahi karte. Log in karne se history save ho sakti hai taake baad mein dekh sakain.",
      section2Title: "Kya hum kisi ko report karte hain?",
      section2Body:
        "Nahi. Panah aik ghair-janibdar maloomati zariya hai. Hum kisi teesray fareeq ko aap ki pehchaan ya sawaalat nahi batate.",
      section3Title: "Kya app mujhe judge karti hai?",
      section3Body:
        "Nahi. Hamara maqsad sirf madad karna hai. Koi sawaal chhota ya bara nahi.",
    },
    auth: {
      title: "Panah mein jari rakhein",
      subtitle: "Apni guftagu save karein aur jahan se chhoda tha wahan se shuru karein.",
      phoneLabel: "Mobile number",
      phonePlaceholder: "3XX XXXXXXX",
      sendCode: "Code bhejein",
      otpLabel: "OTP code",
      otpPlaceholder: "6-digit code",
      verify: "Verify karein aur jari rakhein",
      changeNumber: "Doosra number istemal karein",
      footnote: "Password ki zaroorat nahi, sirf aap ka number aur aik code.",
      error: "Kuch ghalat ho gaya. Barah-e-karam dobara koshish karein.",
    },
  },
};

const LS_LANG_KEY = "panah_lang";
const DEFAULT_LANG = "ur";

function getLang() {
  const stored = localStorage.getItem(LS_LANG_KEY);
  return I18N[stored] ? stored : DEFAULT_LANG;
}

function setLang(lang) {
  if (I18N[lang]) {
    localStorage.setItem(LS_LANG_KEY, lang);
    document.documentElement.lang = lang === "ur" ? "ur" : "en";

    /* Keep the chat UI LTR (WhatsApp-style bubbles) regardless of language.
       Apply RTL only on landing/content/auth pages. */
    var isChatPage = !!document.getElementById("app") && !!document.getElementById("chat-header");
    document.documentElement.dir = (lang === "ur" && !isChatPage) ? "rtl" : "ltr";
    document.documentElement.classList.toggle("lang-ur", lang === "ur");

    /* Swap logos when switching to/from Urdu */
    var logos = document.querySelectorAll("[data-logo-ur]");
    for (var i = 0; i < logos.length; i++) {
      logos[i].src = lang === "ur"
        ? logos[i].getAttribute("data-logo-ur")
        : logos[i].getAttribute("data-logo-default");
    }
  }
}

function t(keyPath, lang = getLang()) {
  const keys = keyPath.split(".");
  let value = I18N[lang];
  for (const k of keys) {
    if (value == null) return keyPath;
    value = value[k];
  }
  return typeof value === "string" ? value : keyPath;
}

function applyLanguage(lang = getLang()) {
  setLang(lang);

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const text = t(el.dataset.i18n, lang);
    if (text !== el.dataset.i18n) el.textContent = text;
  });

  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const html = t(el.dataset.i18nHtml, lang);
    if (html !== el.dataset.i18nHtml) el.innerHTML = html;
  });

  document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    el.dataset.i18nAttr.split("|").forEach((part) => {
      const [attr, key] = part.split(":");
      if (attr && key) {
        const value = t(key, lang);
        if (value !== key) el.setAttribute(attr, value);
      }
    });
  });
}

window.PanahI18n = {
  getLang,
  setLang,
  t,
  applyLanguage,
  I18N,
};

// Auto-apply on load for pages that include this script directly.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => applyLanguage());
} else {
  applyLanguage();
}
