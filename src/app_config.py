# src/app_config.py
from datetime import time as dtime

START_DATE = "2025-09-20"              # inclusive, YYYY-MM-DD
SNAPSHOT_LOCAL_TIME = dtime(12, 0, 0)  # 12:00 Europe/Amsterdam

VAULTS = [
    {
        "name": "Morpho USDC Prime",
        "address": "0xe108fbc04852B5df72f9E44d7C29F47e7A993aDd",
        "markets": ["USDC-Morpho"],
        "allocator_eoa": "0xB11FabcF8024a1961BDe291A4ddD128Bb3a8AE60",
        "roles_modifier": "0xD5b66FD462b46B9A08c427ddAf7DC50C05a8dF7d",
        "morpho_address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "market_ids": [
            "0x54efdee08e272e929034a8f26f7ca34b1ebe364b275391169b28c6d7db24dbc8",
            "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49",
            "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc",
            "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64",
            "0x6d2fba32b8649d92432d036c16aa80779034b7469b63abc259b17678857f31c2",
            "0x704e020b95cbf452e7a30545d5f72a241c4238eebf9d1c67657fdd4a488581e0",
            "0x61765602144e91e5ac9f9e98b8584eae308f9951596fd7f5e0f59f21cd2bf664",
            "0xbf02d6c6852fa0b8247d5514d0c91e6c1fbde9a168ac3fd2033028b5ee5ce6d0",
            "0xdb8938f97571aeab0deb0c34cf7e6278cff969538f49eebe6f4fc75a9a111293",
            "0xba3ba077d9c838696b76e29a394ae9f0d1517a372e30fd9a0fc19c516fb4c5a7",
            "0xe4cfbee9af4ad713b41bf79f009ca02b17c001a0c0e7bd2e6a89b1111b3d3f08",
        ],
    },
    {
        "name": "Morpho USDT Yield",
        "address": "0xd4e95092a8f108728c49f32A30f30556896563b5",
        "markets": ["ETH-Morpho"],
        "allocator_eoa": "0x60666de704648C1A2BB95ed81F5c405A90C1EC65",
        "roles_modifier": "0xBE624E814F238FdBc89cb5A8e9E7A7Aa8A1bb019",
        "morpho_address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "market_ids": [
            "0x5c6aaf2dfecf6b2d60ef4ee8192b83c53ade0b35cb8e7f763a83a30db10502d1",
            "0xa921ef34e2fc7a27ccc50ae7e4b154e16c9799d3387076c421423ef52ac4df99",
            "0xe7e9694b754c4d4f7e21faf7223f6fa71abaeb10296a4c43a54a7977149687d2",
            "0xdbffac82c2dc7e8aa781bd05746530b0068d80929f23ac1628580e27810bc0c5",
            "0xcec858380cba2d9ca710fce3ce864d74c3f620d53826f69d08508902e09be86f",
            "0xdc5333039bcf15f1237133f74d5806675d83d9cf19cfd4cfdd9be674842651bf",
            "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",
            "0xb5b0ff0fccf16dff5bef6d2d001d60f5c4ab49df1020a01073d3ad635c80e8d5",
            "0x89c30faadb4d3e748583fe5862b257a9d408f9b64d8e79d4d94b3bd8f2592c1c",
            "0x0f84816cd17292edba65f7c2e88a7aace40dad7cc79399b49b66f7cc81ecdfd2",
        ],
    },
    {
        "name": "Morpho EURC Yield",
        "address": "0x0c6aec603d48eBf1cECc7b247a2c3DA08b398DC1",
        "markets": ["EURC-Morpho"],
        "allocator_eoa": "0xb4b8e57D0B90249200357b1D3734Df4aa1ce8Cfb",
        "roles_modifier": "0xcDDDfC94a6A6f6BbaA3b73cC5b9b652b0D95e182",
        "morpho_address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "market_ids": [
            "0x8b45b8c46b2a8d69fa6a6c1d18154089875a5e7d68977ad7b14099b6660e51c2",
            "0x7384bd82fb2f2a562555d4aab25583b4e40deed124b7c95dc16be34547434193",
            "0x7421c2741e064e8c53fcb5de9faf7f0025dce75bc1caf26774dd878291c81dac",
            "0xff527fe9c6516f9d82a3d51422ccb031d123266e6e26d4c22c942a948c180a75",
        ],
    },
]