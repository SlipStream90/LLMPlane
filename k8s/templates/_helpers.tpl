{{/*
Expand the name of the chart.
*/}}
{{- define "llmplane.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "llmplane.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "llmplane.labels" -}}
helm.sh/chart: {{ include "llmplane.name" . }}-{{ .Chart.Version }}
{{ include "llmplane.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "llmplane.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llmplane.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Image helper
*/}}
{{- define "llmplane.image" -}}
{{- $registry := .global.imageRegistry -}}
{{- $prefix := .global.imagePrefix -}}
{{- $tag := .tag | default "latest" -}}
{{- printf "%s/%s/%s:%s" $registry $prefix .name $tag -}}
{{- end }}
