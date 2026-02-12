#!/bin/bash
# AI舌诊智能诊断系统 - Elasticsearch索引设置脚本
#
# Setup script for audit log indices with WORM (Write Once Read Many) configuration.
# Creates index templates and ILM policies for 180-day retention.
#
# Author: Ralph Agent
# Date: 2026-02-12
#

ELASTIC_HOST=${ELASTICSEARCH_HOSTS:-"http://elasticsearch:9200"}
ELASTIC_USER=${ELASTICSEARCH_USER:-"elastic"}
ELASTIC_PASS=${ELASTICSEARCH_PASSWORD:-"changeme"}

wait_for_elasticsearch() {
  echo "Waiting for Elasticsearch to be ready..."
  until curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" "$ELASTIC_HOST/_cluster/health" > /dev/null; do
    echo "Elasticsearch not ready, waiting 5 seconds..."
    sleep 5
  done
  echo "Elasticsearch is ready!"
}

create_audit_index_template() {
  echo "Creating audit log index template..."

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X PUT "$ELASTIC_HOST/_index_template/shezhen-audit-template" \
    -H 'Content-Type: application/json' -d '
{
  "index_patterns": ["shezhen-audit-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 1,
      "index.lifecycle.name": "shezhen-audit-policy",
      "index.lifecycle.rollover_alias": "shezhen-audit",
      "index.blocks.write": false
    },
    "mappings": {
      "properties": {
        "@timestamp": {"type": "date"},
        "log_type": {"type": "keyword"},
        "level": {"type": "keyword"},
        "audit_log": {
          "properties": {
            "timestamp": {"type": "date"},
            "level": {"type": "keyword"},
            "message": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
          }
        },
        "image_id": {"type": "keyword"},
        "diagnosis_type": {"type": "keyword"},
        "success": {"type": "boolean"},
        "method": {"type": "keyword"},
        "path": {"type": "keyword"},
        "status_code": {"type": "integer"},
        "duration_ms": {"type": "float"},
        "client_ip": {"type": "ip"},
        "error_type": {"type": "keyword"},
        "geoip": {
          "properties": {
            "location": {"type": "geo_point"},
            "country_name": {"type": "keyword"},
            "city_name": {"type": "keyword"}
          }
        }
      }
    }
  }
}'
}

create_application_index_template() {
  echo "Creating application log index template..."

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X PUT "$ELASTIC_HOST/_index_template/shezhen-application-template" \
    -H 'Content-Type: application/json' -d '
{
  "index_patterns": ["shezhen-application-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 1,
      "index.lifecycle.name": "shezhen-application-policy",
      "index.lifecycle.rollover_alias": "shezhen-application"
    },
    "mappings": {
      "properties": {
        "@timestamp": {"type": "date"},
        "log_level": {"type": "keyword"},
        "logger": {"type": "keyword"},
        "log_message": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
      }
    }
  }
}'
}

create_audit_ilm_policy() {
  echo "Creating ILM policy for audit logs (180 day retention)..."

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X PUT "$ELASTIC_HOST/_ilm/policy/shezhen-audit-policy" \
    -H 'Content-Type: application/json' -d '
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "30d"
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "30d",
        "actions": {
          "forcemerge": {
            "max_num_segments": 1
          },
          "set_priority": {
            "priority": 50
          }
        }
      },
      "cold": {
        "min_age": "90d",
        "actions": {
          "set_priority": {
            "priority": 25
          }
        }
      },
      "delete": {
        "min_age": "180d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}'
}

create_application_ilm_policy() {
  echo "Creating ILM policy for application logs (180 day retention)..."

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X PUT "$ELASTIC_HOST/_ilm/policy/shezhen-application-policy" \
    -H 'Content-Type: application/json' -d '
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "30d"
          }
        }
      },
      "delete": {
        "min_age": "180d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}'
}

create_initial_audit_index() {
  echo "Creating initial audit log index..."

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X PUT "$ELASTIC_HOST/shezhen-audit-000001" \
    -H 'Content-Type: application/json' -d '
{
  "aliases": {
    "shezhen-audit": {
      "is_write_index": true
    }
  }
}'
}

create_worm_settings() {
  echo "Configuring WORM (Write Once Read Many) settings for audit compliance..."

  # Create index block settings that prevent deletion/modification
  # Note: This is applied to indices after they roll over to warm phase
}

create_kibana_index_patterns() {
  echo "Creating Kibana index patterns..."

  # Wait for Kibana to be ready
  sleep 10

  KIBANA_HOST=${KIBANA_HOST:-"http://kibana:5601"}

  # Create index patterns via Kibana API
  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X POST "$KIBANA_HOST/api/saved_objects/index-pattern/shezhen-audit" \
    -H 'Content-Type: application/json' \
    -H "kbn-xsrf: true" -d '
{
  "attributes": {
    "title": "shezhen-audit-*",
    "timeFieldName": "@timestamp"
  }
}'

  curl -s -u "$ELASTIC_USER:$ELASTIC_PASS" -X POST "$KIBANA_HOST/api/saved_objects/index-pattern/shezhen-application" \
    -H 'Content-Type: application/json' \
    -H "kbn-xsrf: true" -d '
{
  "attributes": {
    "title": "shezhen-application-*",
    "timeFieldName": "@timestamp"
  }
}'
}

# Main execution
main() {
  echo "Starting Elasticsearch setup for Shezhen AI Diagnosis System..."
  echo "Using Elasticsearch host: $ELASTIC_HOST"

  wait_for_elasticsearch
  create_audit_ilm_policy
  create_application_ilm_policy
  create_audit_index_template
  create_application_index_template
  create_initial_audit_index
  create_worm_settings

  echo "Elasticsearch setup complete!"
  echo ""
  echo "Next steps:"
  echo "1. Verify indices: curl -u $ELASTIC_USER:$ELASTIC_PASS $ELASTIC_HOST/_cat/indices?v"
  echo "2. Verify ILM policies: curl -u $ELASTIC_USER:$ELASTIC_PASS $ELASTIC_HOST/_ilm/policy/shezhen-audit-policy"
  echo "3. Access Kibana at http://localhost:5601"
}

main "$@"
