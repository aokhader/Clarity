// Mirrors backend/app/schemas.py. Change both files in one commit.

export type HealthOut = {
  status: 'ok'
  clio_configured: boolean
  models_configured: boolean
}
