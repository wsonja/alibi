/** Classify a piece of evidence by its name so the UI can draw a simple icon for it. */

export type EvidenceKind =
  | 'bottle'
  | 'letter'
  | 'book'
  | 'jar'
  | 'ash'
  | 'case'
  | 'jewel'
  | 'paper'
  | 'key'
  | 'weapon'
  | 'phone'
  | 'photo'
  | 'glass'
  | 'footprint'
  | 'clue'

const RULES: Array<[RegExp, EvidenceKind]> = [
  [/\b(decanter|bottle|brandy|wine|whisky|whiskey|flask|vial|phial)\b/i, 'bottle'],
  [/\b(glass|tumbler|cup|mug)\b/i, 'glass'],
  [/\b(letter|note|envelope|telegram|memo|email|message)\b/i, 'letter'],
  [/\b(ledger|book|diary|journal|notebook|accounts|records)\b/i, 'book'],
  [/\b(jar|tin|canister|powder|chemical|cyanide|arsenic|poison)\b/i, 'jar'],
  [/\b(ash|ashes|cigar|cigarette|burn|burned|burnt|grate|ember)\b/i, 'ash'],
  [/\b(case|box|satchel|bag|briefcase|wallet|purse)\b/i, 'case'],
  [/\b(clasp|necklace|pearl|ring|brooch|earring|jewel|locket|watch|cufflink)\b/i, 'jewel'],
  [/\b(reference|receipt|ticket|paper|document|contract|will|deed|page|torn)\b/i, 'paper'],
  [/\b(key|keys|lock)\b/i, 'key'],
  [/\b(knife|dagger|pistol|revolver|gun|blade|poker|rope|candlestick|hammer|wrench)\b/i, 'weapon'],
  [/\b(phone|telephone|laptop|computer|usb|drive|badge|card)\b/i, 'phone'],
  [/\b(photo|photograph|print|negative|picture|portrait)\b/i, 'photo'],
  [/\b(footprint|footprints|shoe|shoes|boot|mud|track|tracks|glove|gloves)\b/i, 'footprint'],
]

export function evidenceKind(name: string, description = ''): EvidenceKind {
  const hay = `${name} ${description}`
  for (const [re, kind] of RULES) if (re.test(hay)) return kind
  return 'clue'
}
