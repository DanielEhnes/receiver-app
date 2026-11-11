# receiver-app

A small FastAPI app with a web page for uploading files and folders to an S3-compatible bucket. All objects go under `upload/`:

| Type  | Endpoint              | Accepts         | Stored at |
|-------|-----------------------|-----------------|-----------|
| ZIP   | `POST /upload/zip`    | `.zip`          | `upload/zip/<path>.zip`, plus the extracted files at `upload/zip/<path>/...` |
| Excel | `POST /upload/xlsx`   | valid `.xlsx`   | `upload/xlsx/<path>` |
| Other | `POST /upload/other`  | anything        | `upload/other/<path>` |

Folder uploads keep their folder structure. Each endpoint returns `{"uploaded": [...keys], "rejected": [{file, reason}]}`.

HTTP Basic auth protects everything except `GET /healthz`. There is one username and password, set in `APP_USERNAME` and `APP_PASSWORD`.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
copy .env.example .env          # then fill in S3 endpoint, keys, bucket, login
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080 and log in.

Upload with curl:

```bash
curl -u user:pass -F "files=@report.xlsx" http://localhost:8080/upload/xlsx
curl -u user:pass -F "files=@data.zip"    http://localhost:8080/upload/zip
```

## Settings

| Variable | Where | Notes |
|----------|-------|-------|
| `S3_ENDPOINT_URL` | ConfigMap | e.g. `https://s3.example.internal:9000` |
| `S3_BUCKET` | ConfigMap | |
| `S3_REGION` | ConfigMap | default `us-east-1` |
| `S3_ROOT_PREFIX` | ConfigMap | default `upload/` |
| `S3_CA_BUNDLE` | ConfigMap | optional path to a CA certificate for a private-CA endpoint |
| `S3_VERIFY_SSL` | ConfigMap | default `true` |
| `S3_CREATE_BUCKET` | ConfigMap | create the bucket on startup; default `false` |
| `MAX_UNZIPPED_BYTES` | ConfigMap | zips that extract to more than this are rejected (default 1 GiB) |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Secret | |
| `APP_USERNAME`, `APP_PASSWORD` | Secret | login for the web page and API |

## Deploy to OpenShift

1. **Build and push the image.** Either:
   ```bash
   podman build -t <registry>/<namespace>/receiver-app:0.1 -f Containerfile .
   podman push <registry>/<namespace>/receiver-app:0.1
   ```
   or build inside the cluster:
   ```bash
   oc new-build --name receiver-app --binary --strategy=docker --to receiver-app:0.1
   oc patch bc/receiver-app -p '{"spec":{"strategy":{"dockerStrategy":{"dockerfilePath":"Containerfile"}}}}'
   oc start-build receiver-app --from-dir=. --follow
   ```
2. Set the image in `openshift/deployment.yaml` and the S3 settings in `openshift/configmap.yaml`.
3. **Create the secret.** Copy `openshift/secret.yaml.example` to `openshift/secret.yaml` and fill it in. The real file is git-ignored. You can also use `oc create secret generic ...` as shown in the example file.
4. Apply everything with `oc apply -f openshift/`, then wait with `oc rollout status deploy/receiver-app`.
5. Get the URL with `oc get route receiver-app`. The Route terminates TLS and redirects HTTP to HTTPS.

### OpenShift notes
- **Upload timeouts:** the Route sets `haproxy.router.openshift.io/timeout: 10m`. Raise it if large uploads still fail.
- **Temporary disk:** uploads are buffered in `/tmp` (an `emptyDir` limited to 2Gi). Raise `sizeLimit` and `ephemeral-storage` together for bigger files.
- **Private-CA S3 endpoint:** run `oc create configmap s3-ca --from-file=ca.crt=./ca.crt`. Then uncomment the `s3-ca` volume and its mount in `deployment.yaml`, and set `S3_CA_BUNDLE=/etc/s3-ca/ca.crt` in the ConfigMap.
- **Network:** the S3 host is outside the cluster, so pods need egress to it. Check EgressFirewall and NetworkPolicy. If the cluster uses an HTTP proxy, add the S3 host to `NO_PROXY`.
- **Testing the image locally** the way OpenShift runs it, with a random UID:
  `podman run --rm --user 12345:0 -p 8080:8080 --env-file .env receiver-app:0.1`
