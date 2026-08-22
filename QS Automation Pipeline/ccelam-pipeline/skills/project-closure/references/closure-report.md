# Project Closure Report — Structure

The CCELAM closing instrument. Document ref
`CCELAM/CLO/[PROJECT]/[YEAR]/[SEQ] Rev [N]`. A4 portrait, house brand,
British English, third-person passive voice, mandatory sign-off block.

## Sections

1. **Cover and Executive Summary** — final contract sum vs original;
   out-turn vs the elemental cost plan; time performance; headline lessons.

2. **Commercial Performance**
   - Cost: original sum → approved VOs → determined claims → final sum;
     variance % and the three largest drivers
   - Out-turn vs cost plan: per NRM1 element, planned vs final cost/m² GFA
     (this is the test of Stage 3's prediction — report it honestly, with
     uncertainty noted per the RICS Cost prediction professional standard)
   - Cash flow: certificate profile against the appraisal projection

3. **Variations Analysis** — count, gross value, % of contract sum;
   causes classified (design development / employer change / site
   conditions / errors-omissions); claim-vs-assessment gap statistics
   (what the contractor claimed against what was certified — the QS's
   assessment discipline made visible).

4. **Claims and Disputes History** — each claim: Sub-Clause basis,
   claimed, determined, resolution route; open risks transferred to the
   Employer at closure (nil, ideally).

5. **Completion and Defects Record** — TOC and PC dates vs programme;
   defects raised / remedied / resolved under 11.4; DNP extensions.

6. **Out-Turn Rate Analysis** — the rate library feedback: items where
   the certified out-turn evidence materially moves the library rate;
   star rates created during the project; confirmation that the out-turn
   hook has been run and the library revision reference.

7. **Lessons Learned** — measurement (model quality, GUID coverage,
   intake gate findings), procurement, contract administration; each
   lesson assigned an owner and a pipeline stage it improves.

8. **Archive and Handover Schedule** — closing ledger snapshot Rev and
   SHA-256; certificate register; drawing/model issue register; statutory
   and warranty documents; where each is archived.

9. **Sign-off block.**

## Data discipline

Sections 2–6 are generated from the ledger (`state()`, event log,
`out_turn_rates()`) — the report writer adds narrative and judgement, not
figures. Where a figure in the report cannot be traced to a ledger event,
it does not go in the report.
