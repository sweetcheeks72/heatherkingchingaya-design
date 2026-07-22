(() => {
  "use strict";

  const form = document.querySelector("#inquiry-form");
  if (!form) return;

  const fields = document.querySelector("#form-fields");
  const reviewPanel = document.querySelector("#review-panel");
  const confirmationPanel = document.querySelector("#confirmation-panel");
  const summary = document.querySelector("#review-summary");
  const error = document.querySelector("#form-error");
  const editButton = document.querySelector("#edit-inquiry");
  const confirmButton = document.querySelector("#confirm-inquiry");
  const startOverButton = document.querySelector("#start-over");

  const labels = {
    projectType: "Project type",
    services: "Support",
    budget: "Investment range",
    name: "Name",
    email: "Email",
    location: "Project location",
    details: "Space notes"
  };

  function valuesFromForm() {
    const data = new FormData(form);
    return {
      projectType: data.get("projectType") || "—",
      services: data.getAll("services").join(", ") || "Not specified",
      budget: data.get("budget") || "—",
      name: data.get("name") || "—",
      email: data.get("email") || "—",
      location: data.get("location") || "Not specified",
      details: data.get("details") || "Not specified"
    };
  }

  function validate() {
    const required = [
      { selector: '[name="projectType"]', message: "Choose a project type." },
      { selector: '[name="budget"]', message: "Choose an investment range." },
      { selector: "#name", message: "Enter your name." },
      { selector: "#email", message: "Enter a valid email address." }
    ];

    for (const item of required) {
      const controls = [...form.querySelectorAll(item.selector)];
      const valid = controls.some((control) => control.type === "radio" ? control.checked : control.checkValidity());
      if (!valid) {
        error.textContent = item.message;
        error.hidden = false;
        controls[0].focus();
        return false;
      }
    }

    error.hidden = true;
    error.textContent = "";
    return true;
  }

  function renderSummary() {
    summary.replaceChildren();
    const values = valuesFromForm();
    Object.entries(values).forEach(([key, value]) => {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = labels[key];
      description.textContent = value;
      row.append(term, description);
      summary.append(row);
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!validate()) return;
    renderSummary();
    fields.hidden = true;
    reviewPanel.hidden = false;
    reviewPanel.querySelector("h3").focus({ preventScroll: true });
    reviewPanel.scrollIntoView({ block: "start" });
  });

  editButton.addEventListener("click", () => {
    reviewPanel.hidden = true;
    fields.hidden = false;
    form.querySelector("#name").focus({ preventScroll: true });
    form.scrollIntoView({ block: "start" });
  });

  confirmButton.addEventListener("click", () => {
    reviewPanel.hidden = true;
    confirmationPanel.hidden = false;
    confirmationPanel.focus();
  });

  startOverButton.addEventListener("click", () => {
    form.reset();
    confirmationPanel.hidden = true;
    fields.hidden = false;
    error.hidden = true;
    form.querySelector('[name="projectType"]').focus();
  });
})();

