// Ask before submitting forms marked with data-confirm.
document.querySelectorAll("form[data-confirm]").forEach(form => {
  form.addEventListener("submit", e => {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// Disable submit controls only after every validation handler has accepted the form.
document.querySelectorAll("form").forEach(form => {
  form.addEventListener("submit", e => {
    if (form.dataset.submitting === "true") {
      e.preventDefault();
      return;
    }
    setTimeout(() => {
      if (e.defaultPrevented) return;
      form.dataset.submitting = "true";
      form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(control => {
        control.disabled = true;
      });
    }, 0);
  });
});

// Restore forms when a browser returns to a cached page after submission.
window.addEventListener("pageshow", () => {
  document.querySelectorAll('form[data-submitting="true"]').forEach(form => {
    delete form.dataset.submitting;
    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(control => {
      control.disabled = false;
    });
  });
});

// Warn before uploading a file larger than data-max-mb.
document.querySelectorAll('input[type="file"][data-max-mb]').forEach(input => {
  input.addEventListener("change", () => {
    const file = input.files[0];
    const tooBig = file && file.size > Number(input.dataset.maxMb) * 1024 * 1024;
    input.setCustomValidity(tooBig ? "File is larger than " + input.dataset.maxMb + " MB." : "");
    if (tooBig) input.reportValidity();
  });
});