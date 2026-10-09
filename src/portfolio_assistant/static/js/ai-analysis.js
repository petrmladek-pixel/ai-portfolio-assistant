function portfolioStrategicAnalysis(portfolioId, personaPrompts) {
  return {
    currentPortfolioId: portfolioId,
    personaPrompts: personaPrompts || {},
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

    get selectedPersonaPrompt() {
      return this.personaPrompts[this.selectedPersona] || "";
    },

    async init() {
      this.showEmptyState();
      await this.loadInvestorContext();
      await this.loadCachedAnalysis();
    },

    async loadInvestorContext() {
      const response = await fetch("/api/settings/investor-context");
      if (!response.ok) return;
      const payload = await response.json();
      this.userContext = payload.investor_context || "";
    },

    async saveInvestorContext() {
      const response = await fetch("/api/settings/investor-context", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ investor_context: this.userContext }),
      });
      if (!response.ok) {
        throw new Error("Investor context could not be saved.");
      }
    },

    showEmptyState() {
      this.analysisResult = "";
      this.analysisCached = false;
      this.createdAt = null;
      this.htmlContent = this.renderMarkdown(
        "## Připraveno k analýze\nVyberte personu a spusťte hloubkový report.",
      );
    },

    async loadCachedAnalysis() {
      if (!this.currentPortfolioId) {
        return;
      }

      this.errorMessage = "";
      try {
        const analysisPath = this.currentPortfolioId === "all"
          ? "/api/portfolios/ai-analysis/all"
          : this.currentPortfolioId === "demo"
            ? "/api/portfolios/demo/ai-analysis"
            : `/api/portfolios/${this.currentPortfolioId}/ai-analysis`;
        const response = await fetch(
          analysisPath,
          { headers: { Accept: "application/json" } },
        );
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(payload?.detail || "Analýzu se nepodařilo načíst.");
        }
        if (!payload) {
          this.showEmptyState();
          return;
        }

        this.analysisResult = payload.analysis_text;
        this.analysisCached = payload.cached;
        this.createdAt = payload.created_at;
        this.selectedPersona = payload.persona_id;
        this.htmlContent = this.renderMarkdown(this.analysisResult);
      } catch (error) {
        this.errorMessage = error.message || "Analýzu se nepodařilo načíst.";
      }
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
        await this.saveInvestorContext();
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
