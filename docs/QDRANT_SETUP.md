# Qdrant Setup Guide — Moneypal Genesis Buildathon

---

## Step 1: Connect to the Right WiFi

You must be on one of these networks to reach the Qdrant server:

```
Aroha_T1
Aroha_G1
```

If you are on any other network, you will not be able to reach Qdrant. Check your WiFi before anything else.

---

## Step 2: Add This to Your `.env` File

Every module (Team A, B, C) must have this in their `.env`:

```
QDRANT_HOST=192.168.1.183
QDRANT_PORT=6333
GROQ_API_KEY=your_key_here
```

Do not use `localhost`. Do not use `127.0.0.1`. Use `192.168.1.183` exactly.

---

## Step 3: Verify You Can Reach Qdrant

Before writing any code, run this in your terminal:

```bash
curl http://192.168.1.183:6333/health
```

You should get back:

```json
{"title":"qdrant - vector search engine","version":"...","commit":"..."}
```

If you get a connection refused or timeout — check your WiFi first, then ask the Integration Lead.

---

## The Running Container (For Reference)

```
Container:  company-intelligence-qdrant
Image:      qdrant/qdrant:latest
Ports:      0.0.0.0:6333-6334 → 6333-6334
Status:     Up (running)
```

You do not need to start or stop anything. The container is already running.

---

## Collection Naming Rules (Must Follow)

Every team creates their own collections. Existing collections in this Qdrant instance belong to other projects — do not touch them.

### Team A — Macro Intelligence
```
macro_intel
```

### Team B — Competitive Intelligence
```
comp_ksfc
comp_kscab
comp_kinara_capital
comp_national_coop
comp_belagavi_dccb
comp_belgaum_industrial
comp_kaujalgi
comp_bellary_urban
comp_bhatkal_urban
comp_scdcc
comp_sidbi
```

### Team C — Regulatory Intelligence
```
reg_master_directions
reg_prudential_norms
reg_fair_practices
reg_kyc_aml
reg_digital_lending
reg_outsourcing
reg_governance
reg_information_security
reg_circulars
```

---

## Critical Rule — create_collection Only

When your ingestion script creates a collection, always use `create_collection`.

**Never use `recreate_collection`** — it deletes the collection first before creating it. If you accidentally use the same name as an existing collection from another project, you will wipe it permanently.

```
create_collection   ← SAFE. Creates only if it doesn't exist.
recreate_collection ← DANGEROUS. Do not use.
```

---

## How to Connect in Python

```python
import qdrant_client

client = qdrant_client.QdrantClient(
    host="192.168.1.183",
    port=6333
)

# Verify connection
print(client.get_collections())
```

If this prints a list of collections (even an empty one), you are connected.

---

## View All Collections (Useful for Debugging)

To see all collections currently in Qdrant, run:

```bash
curl http://192.168.1.183:6333/collections
```

This shows every collection across all teams. Use it to verify your collection was created after ingestion.

---

## Check Your Specific Collection

After running ingestion, verify your collection exists and has points:

```bash
# Check collection exists
curl http://192.168.1.183:6333/collections/macro_intel

# Check how many points (vectors) were indexed
curl http://192.168.1.183:6333/collections/macro_intel/points/count
```

If `points_count` is 0 after ingestion — something went wrong. Re-run ingestion and check for errors.

---

## Troubleshooting

**Connection refused**
→ Check you are on Aroha_T1 or Aroha_G1 WiFi

**Collection already exists error**
→ You used `create_collection` on an existing collection — this is safe, just skip creation and proceed to ingestion

**Points count is 0 after ingestion**
→ Your PDF may be scanned (image-only). pypdf cannot read scanned PDFs. Find a text-based version or copy the text manually into a .txt file

**Timeout on large ingestion**
→ Normal for large PDFs. bge-m3 embedding takes time. Let it run, do not interrupt.

**Wrong data coming back in search results**
→ You are querying the wrong collection name. Double-check the collection name in your `.env` or ingestion script matches the naming rules above.

---

## Quick Reference

| What | Value |
|------|-------|
| Server IP | 192.168.1.183 |
| REST port | 6333 |
| gRPC port | 6334 |
| Health check URL | http://192.168.1.183:6333/health |
| Collections URL | http://192.168.1.183:6333/collections |
| WiFi required | Aroha_T1 or Aroha_G1 |
