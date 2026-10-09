# Onboarding del equipo — MAN.OGG (08/10/2026)

Guía para que un integrante deje su PC lista y empiece a trabajar. Copia adaptada de la guía de onboarding del equipo.

## 0. Antes de empezar
- PC con Windows 10/11, 8 GB de RAM o más (Docker consume bastante) y virtualización activada en la BIOS (la necesita Docker/WSL2).
- Cuenta de GitHub aceptada como colaborador en los 2 repos. Las invitaciones llegan por correo o en github.com/notifications.
- **Claude Code necesita un plan Pro, Max, Team o Enterprise, o una cuenta de Console (API).** El plan gratuito de claude.ai no lo incluye. — https://code.claude.com/docs/en/setup

## 1. Instalar (PowerShell, una línea a la vez)
```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id Docker.DockerDesktop -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Python.Python.3.12 -e
winget install --id Microsoft.VisualStudioCode -e
irm https://claude.ai/install.ps1 | iex
```
- **Git** trae Git Bash, que Claude Code usa como shell en Windows.
- **Docker Desktop** corre la base de datos (PostgreSQL + PostGIS) y la API de Django. Así nadie instala GDAL ni PostGIS en Windows.
- **Node.js LTS (22+)** es para el front (React + Vite).
- **Python 3.12** es opcional: el back corre en Docker. Sirve para scripts sueltos, como el OCR de las fotos.
- **IDE del equipo: VS Code, todos** (decidido el 08/10). Al abrir el repo, VS Code ofrece instalar las extensiones recomendadas, que vienen en `.vscode/extensions.json`: Python, Ruff, ESLint, Prettier, Docker y Claude Code. Dile que sí. La configuración compartida (formatear al guardar) viene en `.vscode/settings.json`. Si quieres un ajuste personal, ponlo en tu configuración de usuario, no en el repo.
- Después de instalar: **reinicia la PC** y abre Docker Desktop una vez para que termine de configurar WSL2.

## 2. Configurar (una sola vez)
```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
gh auth login
claude
```
- `gh auth login`: elige GitHub.com → HTTPS → login con navegador.
- `claude`: la primera vez abre el navegador para iniciar sesión con tu cuenta de Claude. Sales con `/exit`.

## 3. Verificar (todo debe imprimir una versión)
```powershell
git --version
gh --version
docker --version
node -v
claude --version
```
`node -v` debe ser v22 o mayor. Si `claude` no se reconoce, abre una terminal nueva. Si sigue sin reconocerse: https://code.claude.com/docs/en/troubleshoot-install

## 4. Clonar los repos
```powershell
mkdir D:\MAN.OGG
cd D:\MAN.OGG
gh repo clone Aquino45/backend-MAN.OGG
gh repo clone Aquino45/frontend-MAN.OGG
```
(Si no tienes disco D:, usa cualquier carpeta que no esté dentro de OneDrive.)

## 5. Levantar el proyecto (cuando BE-001 y FE-001 estén en `main`; hoy los repos están vacíos)
```powershell
cd D:\MAN.OGG\backend-MAN.OGG
copy .env.example .env
docker compose up -d
```
```powershell
cd D:\MAN.OGG\frontend-MAN.OGG
npm install
npm run dev
```
- API: http://localhost:8000 · Front: http://localhost:5173 (puertos definitivos en BE-001 y FE-001).
- En `.env` pon tu propia contraseña local. **El `.env` nunca se sube a git.**

## 6. Flujo diario
1. Toma un Issue asignado a ti en GitHub (`BE-<n>` en el back, `FE-<n>` en el front).
2. Crea tu rama o worktree para ese ticket: `claude --worktree BE-12`, o `git switch -c ticket/BE-012-<slug>`.
3. Arranca Claude Code con el prompt de arranque que te pase Cristhian. Lleva tu canario: «Zapatito roto.» + `ORQ-<tus iniciales>` + tu palabra (ver `docs/CANARIOS.md`). Si Claude no usa el canario, `/clear` y vuelve a empezar.
4. Claude trabaja solo dentro de los «Archivos permitidos» del ticket, con tests, y deja su informe al final del ticket.
5. Abre el PR con `Closes #<n>`. El CI tiene que estar en verde y lo aprueba **Cristhian** (los PRs de Cristhian los aprueba **@Risc117**). Merge con **squash**.
6. Reglas fijas:
   - Nunca push a `main`.
   - Nunca subas `.env` ni claves.
   - **Nunca inventes datos del censo:** los de prueba van marcados `demo: true`.
   - `/clear` entre tareas distintas y después de 2 correcciones fallidas.

## 7. Qué puede hacer ya (mientras llegan DOC-001, BE-001 y FE-001)
- Instalar y verificar todo (pasos 1 a 3) y clonar (paso 4).
- Leer `docs/requerimientos.md`: qué pide el stakeholder, la cartilla de 19 campos y la paleta.
- **Datos del censo:** llenar la plantilla `plantilla-censo-arboreo.xlsx` con los árboles del sector que ya tiene datos. Es el formato de entrada que va a importar el back (la plantilla te la entrega el director; no está en este repo).

## 8. Documentación del equipo
- [AGENTS.md](AGENTS.md): reglas del repo (también para Claude Code, vía [CLAUDE.md](CLAUDE.md)).
- [docs/ESTADO.md](docs/ESTADO.md): estado actual y siguiente ticket.
- [docs/CANARIOS.md](docs/CANARIOS.md): registro de canarios.
- [docs/tickets/](docs/tickets/): un archivo por ticket.

Estos archivos, y esta guía, son del proceso de trabajo: llevan `export-ignore` en `.gitattributes` y no salen en la entrega.
