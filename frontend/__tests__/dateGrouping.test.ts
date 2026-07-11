import { getDateGroupLabel, groupByDate } from "@/components/dashboard/dateGrouping";

const REFERENCE = new Date("2026-07-11T12:00:00Z");

describe("getDateGroupLabel", () => {
  it("labels today, yesterday, and the recent windows", () => {
    expect(getDateGroupLabel("2026-07-11T08:00:00Z", REFERENCE)).toBe("Aujourd'hui");
    expect(getDateGroupLabel("2026-07-10T08:00:00Z", REFERENCE)).toBe("Hier");
    expect(getDateGroupLabel("2026-07-06T08:00:00Z", REFERENCE)).toBe("7 derniers jours");
    expect(getDateGroupLabel("2026-06-20T08:00:00Z", REFERENCE)).toBe("30 derniers jours");
  });

  it("falls back to a capitalized month/year label for older dates", () => {
    expect(getDateGroupLabel("2026-01-05T08:00:00Z", REFERENCE)).toBe("Janvier 2026");
  });
});

describe("groupByDate", () => {
  it("groups consecutive items sharing a label without reordering them", () => {
    const sessions = [
      { id: 1, date_creation: "2026-07-11T08:00:00Z" },
      { id: 2, date_creation: "2026-07-11T09:00:00Z" },
      { id: 3, date_creation: "2026-01-05T08:00:00Z" },
      { id: 4, date_creation: null },
    ];

    const groups = groupByDate(sessions, REFERENCE);

    expect(groups).toEqual([
      { label: "Aujourd'hui", items: [sessions[0], sessions[1]] },
      { label: "Janvier 2026", items: [sessions[2]] },
      { label: "Sans date", items: [sessions[3]] },
    ]);
  });
});
