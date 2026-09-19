function portfolioStrategicAnalysis(portfolioId) {
  return {
    currentPortfolioId: portfolioId,
    selectedPersona: "WARREN_BUFFETT",
    userContext: "",
    forceRefresh: false,
    isAnalyzing: false,
    analysisResult: "",
    analysisCached: false,
    createdAt: null,
    errorMessage: "",
    htmlContent: "",
    copied: false,

    init() {
      this.htmlContent = this.renderMarkdown(
        "## Připraveno k analýze\nVyberte personu a spusťte hloubkový report.",
      );
    },

    renderMarkdown(markdown) {
      if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
        return `<p>${this.escapeHtml(markdown)}</p>`;
      }
      return DOMPurify.sanitize(marked.parse(markdown));
    },

    escapeHtml(value) {
      const element = document.createElement("div");
      element.textContent = value;
      return element.innerHTML;
    },

    async runStrategicAnalysis() {
      if (!this.currentPortfolioId) {
        return;
      }

      this.isAnalyzing = true;
      this.errorMessage = "";
      try {
        const endpoint = this.currentPortfolioId === "all"
          ? "/api/portfolios/ai-analysis/all"
          : `/api/portfolios/${this.currentPortfolioId}/ai-analysis`;
        const response = await fetch(
          endpoint,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
              persona_id: this.selectedPersona,
              user_context: this.userContext.trim() || null,
              force_refresh: this.forceRefresh,
            }),
          },
        );
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.detail || "Analýzu se nepodařilo vytvořit.");
        }

        this.analysisResult = payload.analysis_text;
        this.analysisCached = payload.cached;
        this.createdAt = payload.created_at;
        this.htmlContent = this.renderMarkdown(this.analysisResult);
      } catch (error) {
        this.errorMessage = error.message || "Analýzu se nepodařilo vytvořit.";
      } finally {
        this.isAnalyzing = false;
        this.forceRefresh = false;
      }
    },

    async copyReport() {
      if (!this.analysisResult) {
        return;
      }
      try {
        await navigator.clipboard.writeText(this.analysisResult);
        this.copied = true;
        window.setTimeout(() => {
          this.copied = false;
        }, 2_000);
      } catch {
        this.errorMessage = "Kopírování reportu selhalo. Zkuste jej označit ručně.";
      }
    },

    formatDate(value) {
      if (!value) {
        return "";
      }
      return new Intl.DateTimeFormat("cs-CZ", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value));
    },
  };
}
