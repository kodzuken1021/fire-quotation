(function () {
  "use strict";

  // Keep these in sync with app/validators.py
  const RESTRICT_DOMAINS = true;
  const ALLOWED_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"];
  const ALLOWED_SUFFIXES = [".edu.ph"];
  const FAKE_DOMAINS = ["example.com", "test.com", "fake.com", "sample.com", "yourwebsite.com"];
  const TYPOS = {
    "gmai.com": "gmail.com", "gmial.com": "gmail.com", "gmal.com": "gmail.com", "gamil.com": "gmail.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "hotmial.com": "hotmail.com", "hotmal.com": "hotmail.com",
    "outlok.com": "outlook.com", "outloo.com": "outlook.com", "iclod.com": "icloud.com"
  };

  const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;
  const NAME_RE = /^[A-Za-z'-]{2,20}$/;
  const PHONE_RE = /^09\d{9}$/;
  const COMPANY_RE = /^[A-Za-z0-9 .,&'()\-]{2,100}$/;

  function emailTypoFix(value) {
    const parts = value.toLowerCase().split("@");
    return parts.length === 2 && TYPOS[parts[1]] ? parts[0] + "@" + TYPOS[parts[1]] : "";
  }

  function registerEmail(v) {
    v = v.toLowerCase();
    if (!EMAIL_RE.test(v)) return "Enter a valid email address.";
    const [local, domain] = v.split("@");
    if (local.length < 2) return "The part before @ must be at least 2 characters.";
    const fix = emailTypoFix(v);
    if (fix) return "Did you mean " + fix + "?";
    if (FAKE_DOMAINS.includes(domain)) return "Please use a real email address.";
    if (RESTRICT_DOMAINS && !ALLOWED_DOMAINS.includes(domain) && !ALLOWED_SUFFIXES.some(s => domain.endsWith(s)))
      return "Use a recognized email provider (Gmail, Yahoo, Hotmail, Outlook, iCloud, AOL)";
    return "";
  }

  const RULES = {
    register: {
      first_name: v => NAME_RE.test(v) ? "" : "First name must be 2 to 20 letters (apostrophes and hyphens allowed).",
      last_name: v => NAME_RE.test(v) ? "" : "Last name must be 2 to 20 letters (apostrophes and hyphens allowed).",
      email: registerEmail,
      contact_number: v => !PHONE_RE.test(v) ? "Enter an 11-digit mobile number starting with 09 (example: 09171234567)."
        : /(\d)\1{3,}/.test(v) ? "The number cannot repeat the same digit 4 or more times in a row." : "",
      company_name: v => COMPANY_RE.test(v) ? "" : "Company name must be 2 to 100 characters (letters, numbers and . , & ' ( ) - only).",
      password: v => v.length >= 8 && /\d/.test(v) ? "" : "Password must be at least 8 characters and include a number.",
      confirm_password: (v, form) => v === form.elements.password.value ? "" : "Passwords do not match."
    },
    login: {
      email: v => EMAIL_RE.test(v) ? "" : "Enter a valid email address.",
      password: v => v ? "" : "Enter your password."
    }
  };

  function show(input, message) {
    const box = document.getElementById(input.id + "-error");
    input.classList.toggle("is-invalid", !!message);
    input.classList.toggle("is-valid", !message && input.value !== "");
    if (box) box.textContent = message;
    return !message;
  }

  function check(input, form, rules) {
    const rule = rules[input.name];
    if (!rule) return true;
    const isPassword = input.type === "password" || input.classList.contains("has-toggle");
    const value = isPassword ? input.value : input.value.trim();
    const ok = show(input, rule(value, form));
    if (input.name === "email" && form.dataset.form === "register") suggestEmail(input, form);
    return ok;
  }

  // "Did you mean ...?" button under the email field
  function suggestEmail(input, form) {
    const box = document.getElementById("email-suggest");
    if (!box) return;
    box.textContent = "";
    const fix = emailTypoFix(input.value.trim());
    if (!fix) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-link btn-sm p-0";
    btn.textContent = "Use " + fix;
    btn.addEventListener("click", () => { input.value = fix; box.textContent = ""; check(input, form, RULES.register); });
    box.appendChild(btn);
  }

  // Asks Cloudflare DNS-over-HTTPS whether the email domain exists. Advisory only:
  // the server runs the real MX check when the form is submitted.
  async function checkDomainExists(input) {
    const value = input.value.trim().toLowerCase();
    if (registerEmail(value)) return;
    const domain = value.split("@")[1];
    try {
      const res = await fetch("https://cloudflare-dns.com/dns-query?name=" + encodeURIComponent(domain) + "&type=MX",
        { headers: { accept: "application/dns-json" } });
      const json = await res.json();
      if (input.value.trim().toLowerCase() === value && json.Status === 3)   // 3 = domain does not exist
        show(input, "That email domain does not exist.");
    } catch (e) { /* offline or blocked: skip, the server will check */ }
  }
  // Show / hide password buttons
  document.querySelectorAll(".pw-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.classList.toggle("is-shown", show);
      btn.setAttribute("aria-pressed", String(show));
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  document.querySelectorAll("form[data-form]").forEach(form => {
    const mode = form.dataset.form;
    const rules = RULES[mode];
    const inputs = form.querySelectorAll("input[name]");

    inputs.forEach(input => {
      if (input.name === "contact_number")           // digits only, max 11
        input.addEventListener("input", () => { input.value = input.value.replace(/\D/g, "").slice(0, 11); });

      input.addEventListener("input", () => {
        if (input.classList.contains("is-invalid") || input.classList.contains("is-valid")) check(input, form, rules);
        if (input.name === "password" && form.elements.confirm_password && form.elements.confirm_password.value)
          check(form.elements.confirm_password, form, rules);
      });
      input.addEventListener("blur", () => {
        if (input.value === "" && !input.classList.contains("is-invalid")) return;
        if (check(input, form, rules) && mode === "register" && input.name === "email") checkDomainExists(input);
      });
    });

    form.addEventListener("submit", e => {
      let firstBad = null;
      inputs.forEach(input => { if (!check(input, form, rules) && !firstBad) firstBad = input; });
      if (firstBad) { e.preventDefault(); firstBad.focus(); }
    });
  });
})();
