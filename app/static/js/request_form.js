(function () {
  "use strict";
  const form = document.getElementById("quote-form");
  if (!form) return;

  const itemsError = document.getElementById("items-error");
  const wants = document.getElementById("wants_inspection");
  const box = document.getElementById("inspection-fields");
  const address = document.getElementById("inspection_address");
  const dateInput = document.getElementById("preferred_date");

  form.querySelectorAll(".pick-check").forEach(chk => {
    chk.addEventListener("change", () => {
      const row = chk.closest(".pick-row");
      const qty = row.querySelector(".pick-qty");
      qty.disabled = !chk.checked;
      if (chk.checked && !qty.value) qty.value = 1;
      qty.classList.remove("is-invalid");
      row.classList.toggle("is-on", chk.checked);
      if (chk.checked) itemsError.textContent = "";
    });
  });

    form.querySelectorAll(".pick-qty").forEach(q => {
    q.addEventListener("input", () => {
      q.classList.remove("is-invalid");
      if (!form.querySelector(".pick-qty.is-invalid")) itemsError.textContent = "";
    });
  });

  wants.addEventListener("change", () => box.classList.toggle("d-none", !wants.checked));

  function setError(input, message) {
    const err = document.getElementById(input.id + "-error");
    input.classList.toggle("is-invalid", !!message);
    if (err) err.textContent = message;
    return !message;
  }

  form.addEventListener("submit", e => {
    let firstBad = null;
    const bad = el => { if (!firstBad) firstBad = el; };

    const ticked = [...form.querySelectorAll(".pick-check:checked")];
    if (!ticked.length) {
      itemsError.textContent = "Select at least one product or service.";
      bad(form.querySelector(".pick-check"));
    } else {
      itemsError.textContent = "";
      ticked.forEach(chk => {
        const qty = chk.closest(".pick-row").querySelector(".pick-qty");
        const ok = /^\d+$/.test(qty.value) && +qty.value >= 1 && +qty.value <= 999;
        qty.classList.toggle("is-invalid", !ok);
        if (!ok) {
          itemsError.textContent = "Quantity must be a whole number from 1 to 999 for every selected item.";
          bad(qty);
        }
      });
    }

    if (wants.checked) {
      const a = address.value.trim();
      if (!setError(address, a.length >= 5 && a.length <= 255 ? "" : "Enter the site address (5 to 255 characters).")) bad(address);
      const today = new Date().toISOString().slice(0, 10);
      if (dateInput.value && !setError(dateInput, dateInput.value < today ? "Preferred date cannot be in the past." : "")) bad(dateInput);
    }

    if (firstBad) { e.preventDefault(); firstBad.focus(); }
  });
})();
