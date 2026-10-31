(function () {
  "use strict";
  const form = document.getElementById("quote-builder");
  if (!form) return;

  const MONEY = /^\d{1,7}(\.\d{1,2})?$/;
  const inputs = [...form.querySelectorAll(".money-input")];
  const grand = document.getElementById("grand-total");
  const peso = n => "\u20B1" + n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const raw = input => input.value.replace(/,/g, "").trim();

  function recalc() {
    let total = 0;
    inputs.forEach(input => {
      const v = raw(input);
      const qty = input.classList.contains("charge") ? 1 : +input.dataset.qty;
      const line = MONEY.test(v) ? +v * qty : 0;
      input.closest("tr").querySelector(".line-total").textContent = peso(line);
      total += line;
    });
    grand.textContent = peso(total);
  }

  function setError(input, message) {
    const err = document.getElementById(input.id + "-error");
    input.classList.toggle("is-invalid", !!message);
    if (err) err.textContent = message;
    return !message;
  }

  inputs.forEach(input => input.addEventListener("input", () => {
    if (input.classList.contains("is-invalid")) setError(input, MONEY.test(raw(input)) ? "" : "Enter an amount from 0 to 9,999,999.99.");
    recalc();
  }));

  form.addEventListener("submit", e => {
    let firstBad = null;
    inputs.forEach(input => {
      const ok = setError(input, MONEY.test(raw(input)) ? "" : "Enter an amount from 0 to 9,999,999.99.");
      if (!ok && !firstBad) firstBad = input;
    });
    const date = document.getElementById("valid_until");
    const today = new Date().toISOString().slice(0, 10);
    if (!setError(date, date.value && date.value >= today ? "" : "Choose a date that is today or later.") && !firstBad) firstBad = date;
    if (firstBad) { e.preventDefault(); firstBad.focus(); }
  });

  recalc();
})();