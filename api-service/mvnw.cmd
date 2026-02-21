@ECHO OFF
SETLOCAL

SET "BASEDIR=%~dp0"
SET "WRAPPER_DIR=%BASEDIR%\.mvn\wrapper"
SET "MAVEN_VERSION=3.9.9"
SET "MAVEN_NAME=apache-maven-%MAVEN_VERSION%"
SET "MAVEN_HOME=%WRAPPER_DIR%\%MAVEN_NAME%"
SET "MVN_CMD=%MAVEN_HOME%\bin\mvn.cmd"
SET "DIST_URL=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/%MAVEN_VERSION%/%MAVEN_NAME%-bin.zip"
SET "DIST_FILE=%WRAPPER_DIR%\%MAVEN_NAME%-bin.zip"

IF EXIST "%MVN_CMD%" GOTO RUN_MAVEN

IF NOT EXIST "%WRAPPER_DIR%" mkdir "%WRAPPER_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing '%DIST_URL%' -OutFile '%DIST_FILE%'"
IF ERRORLEVEL 1 (
  ECHO Failed to download Maven from %DIST_URL%
  EXIT /B 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Path '%DIST_FILE%' -DestinationPath '%WRAPPER_DIR%' -Force"
IF ERRORLEVEL 1 (
  ECHO Failed to extract Maven archive %DIST_FILE%
  EXIT /B 1
)

DEL /Q "%DIST_FILE%" >NUL 2>NUL

:RUN_MAVEN
CALL "%MVN_CMD%" %*
ENDLOCAL
