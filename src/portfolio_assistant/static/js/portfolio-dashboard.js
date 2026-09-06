const dashboardColors = [
  "#0f172a",
  "#0f766e",
  "#2563eb",
  "#b45309",
  "#7c3aed",
  "#be123c",
  "#15803d",
  "#475569",
];

function portfolioDashboard(portfolioId) {
  return {
    portfolioId,
    loading: true,
    errorMessage: null,
    allocations: [],
    topPositions: [],

    async init() {
      await this.fetchDashboardData();
    },

    async fetchDashboardData() {
      const allocationsUrl = this.portfolioId === "all"
        ? "/api/portfolios/all/allocations"
        : `/api/portfolios/${this.portfolioId}/allocations`;

      try {
        const response = await fetch(
          allocationsUrl,
          { headers: { Accept: "application/json" } },
        );
        if (!response.ok) {
          throw new Error(
            `Allocation request failed with status ${response.status}.`,
          );
        }

        const payload = await response.json();
        this.allocations = Array.isArray(payload.allocations)
          ? payload.allocations
          : [];
        this.calculateTopPositions();
        this.loading = false;
        await this.$nextTick();
        this.renderSectorChart();
        this.renderRegionChart();
      } catch (error) {
        this.errorMessage = "Unable to load portfolio allocations. Please try again.";
        console.error("Unable to load dashboard allocations:", error);
      } finally {
        this.loading = false;
      }
    },

    calculateTopPositions() {
      this.topPositions = [...this.allocations]
        .sort((first, second) => Number(second.percentage) - Number(first.percentage))
        .slice(0, 5);
    },

    renderSectorChart() {
      this.renderDoughnutChart(this.$refs.sectorCanvas, "sector");
    },

    renderRegionChart() {
      this.renderDoughnutChart(this.$refs.regionCanvas, "region");
    },

    renderDoughnutChart(canvas, property) {
      if (!canvas || typeof Chart === "undefined") {
        return;
      }

      const groupedValues = this.allocations.reduce((groups, allocation) => {
        const label = allocation[property] || allocation.country || "Unknown";
        const value = Number(allocation.market_value);
        groups[label] = (groups[label] || 0) + (Number.isFinite(value) ? value : 0);
        return groups;
      }, {});
      const labels = Object.keys(groupedValues);
      const values = Object.values(groupedValues);

      if (canvas._chart) {
        canvas._chart.destroy();
      }

      canvas._chart = new Chart(canvas, {
        type: "doughnut",
        data: {
          labels,
          datasets: [{
            data: values,
            backgroundColor: labels.map(
              (_, index) => dashboardColors[index % dashboardColors.length],
            ),
            borderColor: "#ffffff",
            borderWidth: 3,
            hoverOffset: 8,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "66%",
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                padding: 14,
                usePointStyle: true,
              },
            },
            tooltip: {
              enabled: true,
              callbacks: {
                label(context) {
                  const total = context.dataset.data.reduce(
                    (sum, value) => sum + Number(value),
                    0,
                  );
                  const percentage = total ? (Number(context.raw) / total) * 100 : 0;
                  return `${context.label}: ${percentage.toFixed(1)}%`;
                },
              },
            },
          },
        },
      });
    },

    formatPercentage(value) {
      return Number(value || 0).toFixed(1);
    },

    progressWidth(value) {
      return Math.min(Math.max(Number(value) || 0, 0), 100);
    },
  };
}
