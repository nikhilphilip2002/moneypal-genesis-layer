"""Policy formulation workspace (GICC Policy Maker).

Synthesises a policy brief across the selected regulation and institution
collections — one grounded generation over multi-collection retrieval.
"""
from genesis_core import rag, make_response

from app.services import institution_loader as il
from app.services import reg_loader as rl


def brief(regulation_ids: list[str], institution_ids: list[str], focus: str):
    regs = [r for r in (rl.load_one(i) for i in regulation_ids) if r]
    insts = [i for i in (il.load_one(x) for x in institution_ids) if i]
    if not regs and not insts:
        return None

    # Retrieve grounded context from every selected collection.
    query = focus or "policy implications for a Karnataka MSME lender under Rs 500 crore"
    chunks: list[dict] = []
    for reg in regs:
        chunks += rag.search(reg["qdrant_collection"], query, top_k=3)
    for inst in insts:
        chunks += rag.search(inst["qdrant_collection"], query, top_k=3)

    reg_names = ", ".join(r["display_name"] for r in regs) or "none"
    inst_names = ", ".join(i["name"] for i in insts) or "none"
    prompt = (
        f"Draft an internal policy brief for GICC's Policy Maker.\n"
        f"Regulatory inputs: {reg_names}.\nCompetitive inputs: {inst_names}.\n"
        f"Policy focus: {query}.\n"
        f"Structure exactly as:\n"
        f"POLICY OBJECTIVE: 1-2 sentences.\n"
        f"REGULATORY BASIS: what the regulations require, cited.\n"
        f"COMPETITIVE CONTEXT: what competitors do, cited.\n"
        f"RECOMMENDED POLICY POSITIONS: 3-5 numbered recommendations for GICC.\n"
        f"IMPLEMENTATION ACTIONS: 3-5 bullets with owners (board / compliance / lending ops).\n"
        f"Actionable, not legal."
    )
    answer = rag.generate(prompt, chunks)

    docs = [r["display_name"] for r in regs] + [f"{i['name']} public disclosures" for i in insts]
    url = (regs[0].get("rbi_url") if regs else None) or (insts[0].get("website") if insts else "#")
    return make_response(
        title=f"Policy Brief — {query[:80]}",
        summary=answer,
        key_points=[
            f"Regulatory inputs: {reg_names}",
            f"Competitive inputs: {inst_names}",
            "Recommendations are draft positions pending board review",
        ],
        document="; ".join(docs) if docs else "Genesis intelligence collections",
        url=url or "#",
        ai_note="",
        confidence="medium",
    )
