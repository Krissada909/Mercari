# Stock Manager — Vercel + Supabase

โฟลเดอร์นี้เชื่อม **Supabase Postgres** แล้วขึ้น **Vercel**

## Env ที่รองรับ

แอปจะอ่าน connection ตามลำดับนี้:

1. `DATABASE_URL`
2. `POSTGRES_URL` ← ที่ Vercel+Supabase มักสร้างให้อัตโนมัติ
3. `POSTGRES_PRISMA_URL`
4. `POSTGRES_URL_NON_POOLING`

ดังนั้นถ้าเชื่อม Supabase ผ่าน Vercel Integration แล้ว **ไม่ต้องสร้าง DATABASE_URL ใหม่** ก็ได้

## Deploy

```bash
cd vercel_deploy
vercel
vercel --prod
```

ตรวจว่าใน Vercel มี `POSTGRES_URL` (หรือ `DATABASE_URL`) แล้ว

## ทดสอบ local

```bash
cd vercel_deploy
copy .env.example .env
# ใส่ POSTGRES_URL / DATABASE_URL จาก Supabase
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## หมายเหตุความปลอดภัย

- อย่า commit ไฟล์ `.env`
- ถ้ารหัสผ่าน/ keys เคยแปะในแชทหรือที่สาธารณะ ให้ **เปลี่ยน Database password** ใน Supabase แล้วอัปเดต env ใหม่
