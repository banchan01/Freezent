from orchestration.graph import build_meta_graph

if __name__ == "__main__":
    app = build_meta_graph()
    # Example input
    init = {
        "ticker": "005930.KS",    # Samsung Elec (example)
        "horizon": "30d",
        "task": "Assess combined risk from news & filings",
        "news_result": None,
        "filing_result": None,
        "final_report": None,
    }
    last = None
    for s in app.stream(init):
        last = s
        print(s)
        print("---")
    print("Final: ", last.get("final", {}).get("final_report"))