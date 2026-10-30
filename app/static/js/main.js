// Ask before submitting forms marked with data-confirm.
document.querySelectorAll("form[data-confirm]").forEach(form => {
  form.addEventListener("submit", e => {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
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