console.log("main.js loaded");

// ---------- Grab DOM elements ----------
const form = document.getElementById("tokenForm");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submitBtn");

const resultCard = document.getElementById("result");
const mintSpan = document.getElementById("mint");
const txidSpan = document.getElementById("txid");
const pumpLink = document.getElementById("pumpLink");
const solscanLink = document.getElementById("solscanLink");
const pumpLinkWrapper = document.getElementById("pumpLinkWrapper");
const solscanLinkWrapper = document.getElementById("solscanLinkWrapper");
const axiomLink = document.getElementById("axiomLink");
const axiomLinkWrapper = document.getElementById("axiomLinkWrapper");
const rawError = document.getElementById("rawError");
const multiResults = document.getElementById("multiResults");

// Import existing coin
const importMintInput = document.getElementById("importMint");
const importMintBtn = document.getElementById("importMintBtn");

// Metadata & image preview
const metadataUriField = document.getElementById("metadataUriField");
const imagePreview = document.getElementById("imagePreview");
const imageInput = form.elements["image"];
const aiImagePrompt = document.getElementById("aiImagePrompt");
const generateImageBtn = document.getElementById("generateImageBtn");
const aiImageStatus = document.getElementById("aiImageStatus");
const aiImageBase64Field = document.getElementById("aiImageBase64");

// Clear form button
const clearFormBtn = document.getElementById("clearFormBtn");

// Theme select
const themeSelect = document.getElementById("themeSelect");

// ---------- Theme handling ----------
(function initTheme() {
  const savedTheme = localStorage.getItem("siteTheme") || "dark";
  document.body.setAttribute("data-theme", savedTheme);
  if (themeSelect) {
    themeSelect.value = savedTheme;
  }
})();

if (themeSelect) {
  themeSelect.addEventListener("change", () => {
    const newTheme = themeSelect.value;
    document.body.setAttribute("data-theme", newTheme);
    localStorage.setItem("siteTheme", newTheme);
  });
}

// ---------- Form submit: create token(s) ----------
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  statusEl.textContent = "";
  resultCard.classList.add("hidden");
  rawError.textContent = "";
  rawError.classList.add("hidden");
  multiResults.innerHTML = "";
  multiResults.classList.add("hidden");

  const formData = new FormData(form);

  submitBtn.disabled = true;
  submitBtn.textContent = "Launching...";
  statusEl.textContent = "Sending request to backend...";

  try {
    const res = await fetch("/api/create-token", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      console.error("Error response:", data);
      statusEl.textContent = data.error || "Failed to create token.";

      if (data.raw) {
        rawError.textContent = data.raw;
        rawError.classList.remove("hidden");
      }

      return;
    }

    // SUCCESS
    statusEl.textContent = "Token(s) created successfully!";
    resultCard.classList.remove("hidden");

    // MULTI-LAUNCH RESPONSE
    if (Array.isArray(data.results)) {
      const items = data.results.map((r, index) => {
        const mint = r.mint || "Unknown";
        const createSig = r.signature || "Unknown";
        const sellSig = r.sell_signature || null;
        const pool = r.pool || "pump";

        const pumpUrl = `https://pump.fun/${mint}`;
        const solscanTokenUrl = `https://solscan.io/token/${mint}`;
        const axiomurl = `https://axiom.trade/meme/${mint}`;
        const createTxUrl =
          createSig && createSig !== "Unknown"
            ? `https://solscan.io/tx/${createSig}`
            : null;
        const sellTxUrl =
          sellSig && sellSig !== "Unknown"
            ? `https://solscan.io/tx/${sellSig}`
            : null;

        return `
          <li>
            <strong>Launch ${index + 1} (${pool})</strong><br>
            Mint: <a href="${pumpUrl}" target="_blank" rel="noopener noreferrer">${mint}</a><br>
            CA: <a href="${axiomurl}" target="_blank" rel="noopener noreferrer">${mint}</a><br>
            Token: <a href="${solscanTokenUrl}" target="_blank" rel="noopener noreferrer">${mint}</a><br>
            Create Tx: ${
              createTxUrl
                ? `<a href="${createTxUrl}" target="_blank" rel="noopener noreferrer">${createSig}</a>`
                : createSig
            }<br>
            ${
              sellTxUrl
                ? `Sell Tx: <a href="${sellTxUrl}" target="_blank" rel="noopener noreferrer">${sellSig}</a>`
                : ""
            }
          </li>
        `;
      });

      multiResults.innerHTML = `<ul>${items.join("")}</ul>`;
      multiResults.classList.remove("hidden");
      return;
    }

    // SINGLE LAUNCH (fallback)
    mintSpan.textContent = data.mint || "Unknown";
    const sig = data.signature || data.txid || "Unknown";
    txidSpan.textContent = sig;

    if (data.mint) {
      pumpLink.href = `https://pump.fun/${data.mint}`;
      pumpLinkWrapper.classList.remove("hidden");

      axiomlink.href = `https://axiom.trade/meme//${data.mint}`;
      axiomLinkWrapper.classList.remove("hidden");

      solscanLink.href = `https://solscan.io/token/${data.mint}`;
      solscanLinkWrapper.classList.remove("hidden");
    }
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Unexpected error. Check console.";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Launch Token";
  }
});

// Quick-select amount buttons
const amountInput = form.elements["amount"];
const amountButtons = document.querySelectorAll(".amountBtn");

amountButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const value = btn.getAttribute("data-value");
    if (amountInput) amountInput.value = value;
  });
});

// ---------- Import existing token metadata ----------
importMintBtn.addEventListener("click", async () => {
  const mint = importMintInput.value.trim();
  if (!mint) {
    statusEl.textContent = "Please paste a token mint address.";
    return;
  }

  statusEl.textContent = "Importing token metadata...";
  resultCard.classList.add("hidden");
  rawError.textContent = "";
  rawError.classList.add("hidden");

  try {
    const res = await fetch("/api/import-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mint }),
    });

    const data = await res.json();
    console.log("Import response:", data);

    if (!res.ok) {
      statusEl.textContent = data.error || "Failed to import token metadata.";
      if (data.raw) {
        rawError.textContent = data.raw;
        rawError.classList.remove("hidden");
      }
      return;
    }

    // Fill fields if available
    if (data.name && form.elements["name"]) {
      form.elements["name"].value = data.name;
    }
    if (data.symbol && form.elements["symbol"]) {
      form.elements["symbol"].value = data.symbol;
    }
    if (data.description && form.elements["description"]) {
      form.elements["description"].value = data.description;
    }
    if (data.twitter && form.elements["twitter"]) {
      form.elements["twitter"].value = data.twitter;
    }
    if (data.telegram && form.elements["telegram"]) {
      form.elements["telegram"].value = data.telegram;
    }
    if (data.website && form.elements["website"]) {
      form.elements["website"].value = data.website;
    }

    // Store metadata URI so backend can reuse image + metadata
    if (data.metadata_uri && metadataUriField) {
      metadataUriField.value = data.metadata_uri;
    }

    // Show imported image preview if available
    if (data.image && imagePreview) {
      imagePreview.src = data.image;
      imagePreview.classList.remove("hidden");
    } else if (imagePreview) {
      imagePreview.src = "";
      imagePreview.classList.add("hidden");
    }
    // Show imported image preview if available
    if (data.image && imagePreview) {
      imagePreview.src = data.image;
      imagePreview.classList.remove("hidden");
    } else if (imagePreview) {
      imagePreview.src = "";
      imagePreview.classList.add("hidden");
    }

    // --- Reset AI image generation state when importing ---
    if (aiImageBase64Field) aiImageBase64Field.value = "";
    if (aiImagePrompt) aiImagePrompt.value = "";
    if (aiImageStatus)
      aiImageStatus.textContent = "Using imported image from token metadata.";

    statusEl.textContent =
      "Metadata and image imported. You can override the image by uploading a new one if you like.";
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Unexpected error while importing.";
  }
});

// ---------- Preview uploaded image and override imported metadata ----------
if (imageInput) {
  imageInput.addEventListener("change", () => {
    const file = imageInput.files && imageInput.files[0];

    if (file) {
      // Clear imported metadata URI because we're using a new image now
      if (metadataUriField) metadataUriField.value = "";

      // Show local preview
      const url = URL.createObjectURL(file);
      imagePreview.src = url;
      imagePreview.classList.remove("hidden");

      // CLEAR AI IMAGE if any
      if (aiImageBase64Field) aiImageBase64Field.value = "";
      if (aiImageStatus) aiImageStatus.textContent = "";
    } else {
      imagePreview.src = "";
      imagePreview.classList.add("hidden");
    }
  });
}
// ---------- Generate image with ChatGPT (OpenAI API) ----------
if (generateImageBtn) {
  generateImageBtn.addEventListener("click", async () => {
    const prompt = aiImagePrompt.value.trim();
    if (!prompt) {
      aiImageStatus.textContent = "Enter a description first.";
      return;
    }

    aiImageStatus.textContent = "Generating image...";
    generateImageBtn.disabled = true;

    try {
      const res = await fetch("/api/generate-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      const data = await res.json();
      console.log("AI image response:", data);

      if (!res.ok) {
        console.error("AI image error:", data);
        aiImageStatus.textContent = data.error || "Failed to generate image.";
        return;
      }

      if (!data.image_base64) {
        aiImageStatus.textContent = "No image returned.";
        return;
      }

      // Store base64 so backend can use it on launch
      if (aiImageBase64Field) {
        aiImageBase64Field.value = data.image_base64;
      }

      // Show in the same preview box
      const dataUrl = "data:image/png;base64," + data.image_base64;
      if (imagePreview) {
        imagePreview.src = dataUrl;
        imagePreview.classList.remove("hidden");
      }

      // Clear uploaded file & imported metadata because AI image overrides them
      if (imageInput) imageInput.value = "";
      if (metadataUriField) metadataUriField.value = "";

      aiImageStatus.textContent =
        "Image generated and will be used for your token.";
    } catch (err) {
      console.error(err);
      aiImageStatus.textContent = "Unexpected error while generating image.";
    } finally {
      generateImageBtn.disabled = false;
    }
  });
}

// ---------- Clear form ----------
clearFormBtn.addEventListener("click", () => {
  // Reset all standard form inputs
  form.reset();

  // Clear hidden metadata URI
  if (metadataUriField) metadataUriField.value = "";

  // Clear image preview
  if (imagePreview) {
    imagePreview.src = "";
    imagePreview.classList.add("hidden");
  }
  if (aiImageBase64Field) aiImageBase64Field.value = "";
  if (aiImagePrompt) aiImagePrompt.value = "";
  if (aiImageStatus) aiImageStatus.textContent = "";

  // Reset UI state
  statusEl.textContent = "";
  resultCard.classList.add("hidden");
  rawError.classList.add("hidden");
  multiResults.classList.add("hidden");

  console.log("Form cleared.");
});
