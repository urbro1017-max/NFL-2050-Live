# NFL 2050 LIVE — Hosted Edition

This package is configured as a Render web service.

## Deploy
1. Put these files in a GitHub repository.
2. In Render, choose **New > Web Service** and connect that repository.
3. Render can read `render.yaml`; otherwise use:
   - Runtime: Python
   - Build command: `echo No dependencies to install`
   - Start command: `python server.py`
4. Deploy.
5. Open the generated `onrender.com` address.

The server binds to `0.0.0.0` and Render's `PORT` environment variable.

## Data
The backend currently targets ESPN event `401872932` (Detroit vs Buffalo, Sep 17 2026) and polls public-facing ESPN game feeds. No private API keys are embedded.

## Note
Render's free web service may spin down after inactivity, so the first load after a period of inactivity can take longer.
