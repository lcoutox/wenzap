"use client";

import { useEffect, useRef, useState } from "react";

// ── Country data ──────────────────────────────────────────────────────────────

type Country = {
  code: string;
  name: string;
  flag: string;
  dialCode: string;
  // regex for the national number (digits only, no dial code)
  pattern: RegExp;
  // visual mask: 9 = digit, rest = literal
  mask: string;
};

const COUNTRIES: Country[] = [
  {
    code: "BR",
    name: "Brasil",
    flag: "🇧🇷",
    dialCode: "+55",
    pattern: /^\d{10,11}$/,
    mask: "(99) 99999-9999",
  },
  {
    code: "US",
    name: "Estados Unidos",
    flag: "🇺🇸",
    dialCode: "+1",
    pattern: /^\d{10}$/,
    mask: "(999) 999-9999",
  },
  {
    code: "PT",
    name: "Portugal",
    flag: "🇵🇹",
    dialCode: "+351",
    pattern: /^\d{9}$/,
    mask: "999 999 999",
  },
  {
    code: "AR",
    name: "Argentina",
    flag: "🇦🇷",
    dialCode: "+54",
    pattern: /^\d{8,11}$/,
    mask: "999 9999 9999",
  },
  {
    code: "CL",
    name: "Chile",
    flag: "🇨🇱",
    dialCode: "+56",
    pattern: /^\d{8,9}$/,
    mask: "9 9999 9999",
  },
  {
    code: "CO",
    name: "Colômbia",
    flag: "🇨🇴",
    dialCode: "+57",
    pattern: /^\d{10}$/,
    mask: "999 999 9999",
  },
  {
    code: "MX",
    name: "México",
    flag: "🇲🇽",
    dialCode: "+52",
    pattern: /^\d{10}$/,
    mask: "999 9999 9999",
  },
];

const DEFAULT_COUNTRY = COUNTRIES[0]; // Brasil

// ── Mask helpers ──────────────────────────────────────────────────────────────

function applyMask(digits: string, mask: string): string {
  let di = 0;
  let result = "";
  for (let mi = 0; mi < mask.length && di < digits.length; mi++) {
    if (mask[mi] === "9") {
      result += digits[di++];
    } else {
      result += mask[mi];
      // If the next char in digits would fill the next slot, keep going;
      // but if we're at a literal and haven't consumed a digit, just add the literal.
    }
  }
  return result;
}

function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

// ── Parse incoming E.164 value → split country + national ────────────────────

function parseValue(
  value: string
): { country: Country; national: string } {
  if (!value) return { country: DEFAULT_COUNTRY, national: "" };

  for (const c of COUNTRIES) {
    if (value.startsWith(c.dialCode)) {
      return { country: c, national: value.slice(c.dialCode.length) };
    }
  }
  return { country: DEFAULT_COUNTRY, national: digitsOnly(value) };
}

// ── Component ─────────────────────────────────────────────────────────────────

type Props = {
  label?: string;
  value: string; // E.164 normalised, e.g. "+5537999999999"
  onChange: (normalized: string) => void;
  required?: boolean;
  error?: string;
};

export function PhoneInput({ label, value, onChange, required, error }: Props) {
  const { country: initialCountry, national: initialNational } = parseValue(value);

  const [country, setCountry] = useState<Country>(initialCountry);
  const [inputValue, setInputValue] = useState(
    initialNational ? applyMask(initialNational, initialCountry.mask) : ""
  );
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleInput(raw: string) {
    const digits = digitsOnly(raw);
    // Limit to max digits the mask can hold
    const maxDigits = country.mask.split("").filter((c) => c === "9").length;
    const capped = digits.slice(0, maxDigits);
    const masked = applyMask(capped, country.mask);
    setInputValue(masked);
    onChange(capped ? `${country.dialCode}${capped}` : "");
  }

  function handleCountrySelect(c: Country) {
    setCountry(c);
    setInputValue("");
    onChange("");
    setOpen(false);
  }

  const inputClass =
    "flex-1 bg-transparent text-sm text-nb-text placeholder:text-nb-muted focus:outline-none min-w-0";

  const maxDigits = country.mask.split("").filter((c) => c === "9").length;
  const placeholder = country.mask.replace(/9/g, "9");

  return (
    <div>
      {label && (
        <label className="block text-xs font-medium text-nb-secondary mb-1.5">
          {label}
          {required && <span className="text-nb-danger ml-0.5">*</span>}
        </label>
      )}

      <div
        className={`
          flex items-center bg-nb-elevated border rounded-xl transition-colors overflow-hidden
          ${error ? "border-nb-danger" : "border-nb-border focus-within:border-nb-primary focus-within:ring-1 focus-within:ring-nb-primary/30"}
        `}
      >
        {/* Country selector */}
        <div className="relative flex-shrink-0" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-2.5 text-sm text-nb-text hover:bg-nb-bg/40 transition-colors border-r border-nb-border cursor-pointer select-none"
            aria-label="Selecionar país"
          >
            <span className="text-base leading-none">{country.flag}</span>
            <span className="text-nb-secondary font-medium tabular-nums">{country.dialCode}</span>
            <svg
              className={`w-3 h-3 text-nb-muted transition-transform ${open ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {open && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-nb-panel border border-nb-border rounded-xl shadow-lg overflow-hidden min-w-[200px]">
              {COUNTRIES.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => handleCountrySelect(c)}
                  className={`
                    w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors cursor-pointer
                    ${c.code === country.code
                      ? "bg-nb-primary/10 text-nb-primary"
                      : "text-nb-text hover:bg-nb-elevated"}
                  `}
                >
                  <span className="text-base">{c.flag}</span>
                  <span className="flex-1">{c.name}</span>
                  <span className="text-nb-muted tabular-nums">{c.dialCode}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* National number input */}
        <input
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          value={inputValue}
          onChange={(e) => handleInput(e.target.value)}
          placeholder={placeholder}
          maxLength={country.mask.length}
          className={`${inputClass} px-3 py-2.5`}
        />
      </div>

      {error && (
        <p role="alert" className="text-nb-danger text-xs mt-1">
          {error}
        </p>
      )}
    </div>
  );
}
