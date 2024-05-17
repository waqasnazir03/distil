# Copyright (C) 2013-2024 Catalyst Cloud Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

MOCK_INVOICE_MERGING_EXISTING_DETAILS = {
    "existing unmerging region": {
        "total_cost": 234.56,
        "total_cost_taxed": 269.74,
        "breakdown": {
            "resource type 1": [
                {
                    "rate": 10,
                    "resource_name": "existing uneffected",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 34.56,
                    "resource_name": "existing uneffected",
                    "cost": 34.56,
                    "cost_taxed": 39.74,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "resource type 2": [
                {
                    "rate": -10,
                    "resource_name": "existing uneffected 2",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "existing uneffected 2",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                }
            ],
        }
    },
    "merging region": {
        "total_cost": 234.56,
        "total_cost_taxed": 269.74,
        "breakdown": {
            "unmerging existing resource": [
                {
                    "rate": 10,
                    "resource_name": "existing unmerging",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 34.56,
                    "resource_name": "existing unmerging",
                    "cost": 34.56,
                    "cost_taxed": 39.74,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "merging resource": [
                {
                    "rate": -10,
                    "resource_name": "existing merging",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "existing merging",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                }
            ],
        }
    }
}

MOCK_INVOICE_MERGING_NEW_DETAILS = {
    "new unmerging region": {
        "total_cost": 765.44,
        "total_cost_taxed": 880.26,
        "breakdown": {
            "resource type 1": [
                {
                    "rate": 10,
                    "resource_name": "new uneffected",
                    "cost": 700,
                    "cost_taxed": 805,
                    "unit": "NZD",
                    "quantity": 70
                },
                {
                    "rate": 65.44,
                    "resource_name": "new uneffected",
                    "cost": 65.44,
                    "cost_taxed": 75.26,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "resource type 2": [
                {
                    "rate": -10,
                    "resource_name": "new uneffected 2",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "new uneffected 2",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                }
            ],
        }
    },
    "merging region": {
        "total_cost": 8765.44,
        "total_cost_taxed": 10080.26,
        "breakdown": {
            "unmerging new resource": [
                {
                    "rate": 10,
                    "resource_name": "new unmerging",
                    "cost": 700,
                    "cost_taxed": 805,
                    "unit": "NZD",
                    "quantity": 70
                },
                {
                    "rate": 65.44,
                    "resource_name": "new unmerging",
                    "cost": 65.44,
                    "cost_taxed": 75.26,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "merging resource": [
                {
                    "rate": 100,
                    "resource_name": "new merging",
                    "cost": 1000,
                    "cost_taxed": 1150,
                    "unit": "NZD",
                    "quantity": 10
                },
                {
                    "rate": 45,
                    "resource_name": "new merging",
                    "cost": 7000,
                    "cost_taxed": 8050,
                    "unit": "NZD",
                    "quantity": 200
                }
            ],
        }
    }
}

MERGE_INVOICE_EXPECTED_RESULTS = {
    "merging region": {
        "total_cost": 9000.0,
        "total_cost_taxed": 10350.0,
        "breakdown": {
            "unmerging new resource": [
                {
                    "rate": 10,
                    "resource_name": "new unmerging",
                    "cost": 700,
                    "cost_taxed": 805,
                    "unit": "NZD",
                    "quantity": 70
                },
                {
                    "rate": 65.44,
                    "resource_name": "new unmerging",
                    "cost": 65.44,
                    "cost_taxed": 75.26,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "unmerging existing resource": [
                {
                    "rate": 10,
                    "resource_name": "existing unmerging",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 34.56,
                    "resource_name": "existing unmerging",
                    "cost": 34.56,
                    "cost_taxed": 39.74,
                    "unit": "NZD",
                    "quantity": 1
                }
            ],
            "merging resource": [
                {
                    "rate": -10,
                    "resource_name": "existing merging",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "existing merging",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 100,
                    "resource_name": "new merging",
                    "cost": 1000,
                    "cost_taxed": 1150,
                    "unit": "NZD",
                    "quantity": 10
                },
                {
                    "rate": 45,
                    "resource_name": "new merging",
                    "cost": 7000,
                    "cost_taxed": 8050,
                    "unit": "NZD",
                    "quantity": 200
                }
            ]
        }
    },
    "new unmerging region": {
        "total_cost": 765.44,
        "total_cost_taxed": 880.26,
        "breakdown": {
            "resource type 2": [
                {
                    "rate": -10,
                    "resource_name": "new uneffected 2",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "new uneffected 2",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                }
            ],
            "resource type 1": [
                {
                    "rate": 10,
                    "resource_name": "new uneffected",
                    "cost": 700,
                    "cost_taxed": 805,
                    "unit": "NZD",
                    "quantity": 70
                },
                {
                    "rate": 65.44,
                    "resource_name": "new uneffected",
                    "cost": 65.44,
                    "cost_taxed": 75.26,
                    "unit": "NZD",
                    "quantity": 1
                }
            ]
        }
    },
    "existing unmerging region": {
        "total_cost": 234.56,
        "total_cost_taxed": 269.74,
        "breakdown": {
            "resource type 2": [
                {
                    "rate": -10,
                    "resource_name": "existing uneffected 2",
                    "cost": -200,
                    "cost_taxed": -230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 10,
                    "resource_name": "existing uneffected 2",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                }
            ],
            "resource type 1": [
                {
                    "rate": 10,
                    "resource_name": "existing uneffected",
                    "cost": 200,
                    "cost_taxed": 230,
                    "unit": "NZD",
                    "quantity": 20
                },
                {
                    "rate": 34.56,
                    "resource_name": "existing uneffected",
                    "cost": 34.56,
                    "cost_taxed": 39.74,
                    "unit": "NZD",
                    "quantity": 1
                }
            ]
        }
    }
}
