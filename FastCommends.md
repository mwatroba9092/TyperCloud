komendy do sprawdzania poprawnosci kodu

1. Manifesty Kubernetes
kubectl kustomize k8s/overlays/dev

2. Deployments
kubectl get deploy -n typercloud-dev
kubectl rollout status deployment/backend -n typercloud-dev

3. Bazy Danych 
kubectl get statefulset,pvc -n typercloud-dev

4. Services, ingress

5. Configmap

6. Probes i zasoby
kubectl get pods -n typercloud-dev
kubectl describe pod <pod> -n typercloud-dev

7. SeciurityContext 

8. Github acctions

# Dodatkowe

B1. NetworkPolicy

B2. PodDisruptionBudget

B3. Helm / Kustomize
kubectl kustomize k8s/overlays/prod | grep -E "replicas|namespace|image:"

B4. Obserwowalnos
curl http://localhost:8000/metrics | grep typercloud

# Specificzne wymagnia
 
C1. Minimalna funkcjonalnosc 
  curl http://localhost:8000/health
  curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/matches
  curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/rankings

C2. Trwałosc danych
kubectl delete pod postgres-0 -n typercloud-dev\

C3. Worker
docker compose logs -f worker

## D1. /health (publiczny)
```bash
curl -i http://localhost:8000/health        # 200 {"status":"ok"}
curl -i http://localhost:8000/api/matches    # 401/403 bez tokenu
```

## D2. Trwałość bazy

K8s:

kubectl delete pod postgres-0 -n typercloud-dev
kubectl rollout status statefulset/postgres -n typercloud-dev

docker compose:

docker compose restart postgres   # wolumen pgdata trwaly

## D3. Kolejka (Redis -> Worker)

docker compose logs -f worker

docker compose exec redis redis-cli PUBLISH match_finished 

# Kuberenetes Komendy

kubectl cluster-info 
kubectl get namespaces 
kubectl kustomize k8s/overlays/dev
kubectl apply -k k8s/overlays/dev

kubectl get pods -n typercloud-dev
kubectl get deploy -n typercloud-dev
kubectl get statefulsets -n typercloud-dev
kubectl get services -n typercloud-dev
kubectl get ingress -n typercloud-dev
kubectl get configmaps -n typercloud-dev
kubectl get secrets -n typercloud-dev
kubectl get pvc -n typercloud-dev

kubectl describe (zasob) <pod> -n typercloud-dev
kubectl logs <pod> -n typercloud-dev
kubectl logs -f <pod> -n typercloud-dev
kubectl exec -it <pod> -n typercloud-dev -- sh (komenda)

kubectl scale deployment (kontener) --replicas=? -n typercloud-dev
kubectl delete pod <pod> -n typercloud-dev
kubectl rollout restart deployment (kontener) -n typercloud-dev

kuebctl port forward svc/backend 9090:8000 -n typercloud-dev
kubectl cp <plik lokalny> typercloud-dev/<pod>:<sciezka>
kubectl get deployment backend -o yaml -n typercloud-dev
kubectl edit deploment worker -n typercloud-dev
kubectl get netpol -n typercloud-dev
kubectl get pdb -n typercloud