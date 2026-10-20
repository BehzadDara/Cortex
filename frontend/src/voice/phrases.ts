export interface SpokenPhrases {
  runCode: string;
  searchWeb: (query: string) => string;
  findImages: (query: string) => string;
  findVideos: (query: string) => string;
  searchWebUnspecified: string;
  failure: string;
}

const ENGLISH: SpokenPhrases = {
  runCode: "I wrote a short Python script for that. Should I run it?",
  searchWeb: (query) => `Should I search the web for ${query}?`,
  findImages: (query) => `Should I look for pictures of ${query} on the web?`,
  findVideos: (query) => `Should I look for videos of ${query} on the web?`,
  searchWebUnspecified: "Should I search the web for that?",
  failure: "Sorry, I ran into a problem answering that.",
};

const PERSIAN: SpokenPhrases = {
  runCode: "یک اسکریپت کوتاه پایتون برایش نوشتم. اجرایش کنم؟",
  searchWeb: (query) => `در وب دربارهٔ ${query} جستجو کنم؟`,
  findImages: (query) => `در وب عکس‌های ${query} را پیدا کنم؟`,
  findVideos: (query) => `در وب ویدیوهای ${query} را پیدا کنم؟`,
  searchWebUnspecified: "در وب جستجو کنم؟",
  failure: "متأسفم، در جواب دادن به این سؤال به مشکل خوردم.",
};

const YES = phrasePattern([
  "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "go ahead", "do it", "please do",
  "allow", "approve", "go for it", "of course", "absolutely", "sounds good",
  "بله", "آره", "باشه", "حتما", "حتماً", "اوکی", "انجام بده", "اجرا کن", "بگرد",
]);

const NO = phrasePattern([
  "no", "nope", "nah", "don't", "do not", "cancel", "deny", "skip", "stop", "never mind",
  "not now", "نه", "نخیر", "نمیخوام", "نمی‌خوام", "لازم نیست", "بیخیال", "ولش کن", "نکن",
]);

const PERSIAN_LETTER = /[\u0600-\u06FF]/g;
const LATIN_LETTER = /[A-Za-z]/g;

export function isPersian(text: string): boolean {
  const persian = text.match(PERSIAN_LETTER)?.length ?? 0;
  const latin = text.match(LATIN_LETTER)?.length ?? 0;
  return persian > latin;
}

export function phrasesFor(text: string): SpokenPhrases {
  return isPersian(text) ? PERSIAN : ENGLISH;
}

export function consentIn(text: string): boolean | null {
  const yes = YES.exec(text)?.index ?? Infinity;
  const no = NO.exec(text)?.index ?? Infinity;
  if (yes === Infinity && no === Infinity) return null;
  return yes < no;
}

function phrasePattern(phrases: string[]): RegExp {
  return new RegExp(
    `(?<![\\p{L}\\p{N}])(${phrases.join("|")})(?![\\p{L}\\p{N}])`,
    "iu",
  );
}
