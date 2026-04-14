from db import get_client
client = get_client()
rows = client.table('zip_summaries').select('*').order('wellness_gap_score', desc=True).execute()
for r in rows.data:
    line = "{zip}  gap={gap:.3f}  biz={biz}  reviews={rev}  | {stmt}".format(
        zip=r['zip_code'],
        gap=r['wellness_gap_score'],
        biz=r['business_count'],
        rev=r['review_count'],
        stmt=r['gap_statement']
    )
    print(line)
