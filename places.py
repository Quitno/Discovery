"""Kenya property-search location catalogue.

Administrative constituencies use the current widely-used constituency names;
Nairobi wards are based on Nairobi City County Assembly's ward-office schedule,
and Kiambu wards on Kiambu County Government's published table. Neighbourhood
names are search aliases, not claims about official administrative boundaries.
"""
import re
import unicodedata

COUNTY_CONSTITUENCIES = {
    "Baringo": ["Tiaty", "Baringo North", "Baringo Central", "Baringo South", "Mogotio", "Eldama Ravine"],
    "Bomet": ["Sotik", "Chepalungu", "Bomet East", "Bomet Central", "Konoin"],
    "Bungoma": ["Mt Elgon", "Sirisia", "Kabuchai", "Bumula", "Kanduyi", "Webuye East", "Webuye West", "Kimilili", "Tongaren"],
    "Busia": ["Teso North", "Teso South", "Nambale", "Matayos", "Butula", "Funyula", "Budalangi"],
    "Elgeyo-Marakwet": ["Marakwet East", "Marakwet West", "Keiyo North", "Keiyo South"],
    "Embu": ["Manyatta", "Runyenjes", "Mbeere North", "Mbeere South"],
    "Garissa": ["Garissa Township", "Balambala", "Lagdera", "Dadaab", "Fafi", "Ijara"],
    "Homa Bay": ["Kasipul", "Kabondo Kasipul", "Karachuonyo", "Rangwe", "Homa Bay Town", "Ndhiwa", "Mbita", "Suba South"],
    "Isiolo": ["Isiolo North", "Isiolo South"],
    "Kajiado": ["Kajiado North", "Kajiado Central", "Kajiado East", "Kajiado West", "Kajiado South"],
    "Kakamega": ["Lugari", "Likuyani", "Malava", "Lurambi", "Navakholo", "Mumias West", "Mumias East", "Matungu", "Butere", "Khwisero", "Shinyalu", "Ikolomani"],
    "Kericho": ["Kipkelion East", "Kipkelion West", "Ainamoi", "Belgut", "Bureti", "Sigowet-Soin"],
    "Kiambu": ["Gatundu North", "Gatundu South", "Githunguri", "Juja", "Kabete", "Kiambaa", "Kiambu", "Kikuyu", "Lari", "Limuru", "Ruiru", "Thika Town"],
    "Kilifi": ["Kilifi North", "Kilifi South", "Kaloleni", "Rabai", "Ganze", "Malindi", "Magarini"],
    "Kirinyaga": ["Mwea", "Gichugu", "Ndia", "Kirinyaga Central"],
    "Kisii": ["Bonchari", "South Mugirango", "Bomachoge Chache", "Bobasi", "Bomachoge Borabu", "Nyaribari Masaba", "Nyaribari Chache", "Kitutu Chache North", "Kitutu Chache South"],
    "Kisumu": ["Kisumu East", "Kisumu West", "Kisumu Central", "Seme", "Nyando", "Muhoroni", "Nyakach"],
    "Kitui": ["Mwingi North", "Mwingi West", "Mwingi Central", "Kitui West", "Kitui Rural", "Kitui Central", "Kitui East", "Kitui South"],
    "Kwale": ["Msambweni", "Lungalunga", "Matuga", "Kinango"],
    "Laikipia": ["Laikipia West", "Laikipia East", "Laikipia North"],
    "Lamu": ["Lamu East", "Lamu West"],
    "Machakos": ["Masinga", "Yatta", "Kangundo", "Matungulu", "Kathiani", "Mavoko", "Machakos Town", "Mwala"],
    "Makueni": ["Mbooni", "Kilome", "Kaiti", "Makueni", "Kibwezi West", "Kibwezi East"],
    "Mandera": ["Mandera West", "Mandera East", "Mandera North", "Mandera South", "Banissa", "Lafey"],
    "Marsabit": ["Saku", "North Horr", "Laisamis", "Moyale"],
    "Meru": ["Igembe South", "Igembe Central", "Igembe North", "Tigania West", "Tigania East", "North Imenti", "Buuri", "Central Imenti", "South Imenti"],
    "Migori": ["Rongo", "Awendo", "Uriri", "Nyatike", "Kuria West", "Kuria East", "Suna East", "Suna West"],
    "Mombasa": ["Changamwe", "Jomvu", "Kisauni", "Nyali", "Likoni", "Mvita"],
    "Murang'a": ["Kangema", "Mathioya", "Kiharu", "Kigumo", "Maragwa", "Kandara", "Gatanga"],
    "Nairobi": ["Westlands", "Dagoretti North", "Dagoretti South", "Lang'ata", "Kibra", "Roysambu", "Kasarani", "Ruaraka", "Embakasi South", "Embakasi North", "Embakasi Central", "Embakasi East", "Embakasi West", "Makadara", "Kamukunji", "Starehe", "Mathare"],
    "Nakuru": ["Naivasha", "Gilgil", "Nakuru Town East", "Nakuru Town West", "Kuresoi North", "Kuresoi South", "Subukia", "Rongai", "Bahati", "Njoro", "Molo"],
    "Nandi": ["Tinderet", "Aldai", "Nandi Hills", "Chesumei", "Emgwen", "Mosop"],
    "Narok": ["Kilgoris", "Emurua Dikirr", "Narok North", "Narok East", "Narok South", "Narok West"],
    "Nyamira": ["Kitutu Masaba", "West Mugirango", "North Mugirango", "Borabu"],
    "Nyandarua": ["Kinangop", "Kipipiri", "Ol Kalou", "Ol Jorok", "Ndaragwa"],
    "Nyeri": ["Tetu", "Kieni", "Mathira", "Othaya", "Mukurweini", "Nyeri Town"],
    "Samburu": ["Samburu West", "Samburu North", "Samburu East"],
    "Siaya": ["Ugenya", "Ugunja", "Alego Usonga", "Gem", "Bondo", "Rarieda"],
    "Taita-Taveta": ["Taveta", "Wundanyi", "Mwatate", "Voi"],
    "Tana River": ["Garsen", "Galole", "Bura"],
    "Tharaka-Nithi": ["Maara", "Chuka/Igambang'ombe", "Tharaka"],
    "Trans Nzoia": ["Kwanza", "Endebess", "Saboti", "Kiminini", "Cherangany"],
    "Turkana": ["Turkana North", "Turkana West", "Turkana Central", "Loima", "Turkana South", "Turkana East"],
    "Uasin Gishu": ["Soy", "Turbo", "Moiben", "Ainabkoi", "Kapseret", "Kesses"],
    "Vihiga": ["Vihiga", "Sabatia", "Hamisi", "Luanda", "Emuhaya"],
    "Wajir": ["Wajir North", "Wajir East", "Wajir West", "Wajir South", "Eldas", "Tarbaj"],
    "West Pokot": ["Kapenguria", "Sigor", "Kacheliba", "Pokot South"],
}

NAIROBI_WARDS = {
    "Ruaraka": ["Baba Dogo", "Utalii", "Mathare North", "Lucky Summer", "Korogocho"],
    "Embakasi South": ["Imara Daima", "Kwa Njenga", "Kwa Reuben", "Pipeline", "Kware"],
    "Embakasi North": ["Kariobangi North", "Dandora Area I", "Dandora Area II", "Dandora Area III", "Dandora Area IV"],
    "Embakasi Central": ["Kayole North", "Kayole Central", "Kayole South", "Komarock", "Matopeni/Spring Valley"],
    "Embakasi East": ["Upper Savannah", "Lower Savannah", "Embakasi", "Utawala", "Mihango"],
    "Embakasi West": ["Umoja I", "Umoja II", "Mowlem", "Kariobangi South", "Maringo/Hamza"],
    "Starehe": ["Pangani", "Ziwani/Kariokor", "Landimawe", "Nairobi South", "Hospital"],
    "Dagoretti North": ["Kilimani", "Kawangware", "Gatina", "Kileleshwa", "Kabiro"],
    "Dagoretti South": ["Mutu-Ini", "Ngando", "Riruta", "Uthiru/Ruthimitu", "Waithaka"],
    "Lang'ata": ["Karen", "Nairobi West", "Mugumu-Ini", "South C", "Nyayo Highrise"],
    "Kibra": ["Laini Saba", "Lindi", "Makina", "Woodley/Kenyatta", "Sarangombe"],
    "Roysambu": ["Githurai", "Kahawa West", "Zimmerman", "Roysambu", "Kahawa"],
    "Kasarani": ["Clay City", "Mwiki", "Kasarani", "Njiru", "Ruai"],
    "Westlands": ["Kitisuru", "Parklands/Highridge", "Karura", "Kangemi", "Mountain View"],
    "Makadara": ["Viwandani", "Harambee", "Makongeni", "Pumwani", "Eastleigh North"],
    "Kamukunji": ["Eastleigh South", "Airbase", "California", "Ngara", "Nairobi Central"],
    "Mathare": ["Mabatini", "Huruma", "Ngei", "Mlango Kubwa", "Kiamaiko"],
}

KIAMBU_WARDS = {
    "Gatundu North": ["Gituamba", "Githobokoni", "Chania", "Mang'u"],
    "Gatundu South": ["Kiamwangi", "Kiganjo", "Ndarugo", "Ngenda"],
    "Githunguri": ["Githunguri", "Githiga", "Ikinu", "Ngewa", "Komothai"],
    "Juja": ["Murera", "Theta", "Juja", "Witeithie", "Kalimoni"],
    "Kabete": ["Gitaru", "Muguga", "Nyathuna", "Kabete", "Uthiru"],
    "Kiambaa": ["Cianda", "Karuri", "Ndenderu", "Muchatha", "Kihara"],
    "Kiambu": ["Ting'ang'a", "Ndumberi", "Riabai", "Township"],
    "Kikuyu": ["Karai", "Nachu", "Sigona", "Kikuyu", "Kinoo"],
    "Lari": ["Kinale", "Kijabe", "Nyanduma", "Kamburu", "Lari/Kirenga"],
    "Limuru": ["Bibirioni", "Limuru Central", "Ndeiya", "Limuru East", "Ngecha/Tigoni"],
    "Ruiru": ["Gitothua", "Biashara", "Gatongora", "Kahawa/Sukari", "Kahawa Wendani", "Kiuu", "Mwiki", "Mwihoko"],
    "Thika Town": ["Township", "Kamenu", "Hospital", "Gatuanyaga", "Ngoliba"],
}

# Popular fine-search names. These are property-market neighbourhood aliases, not all official wards.
FINE_AREAS = {
    "Nairobi": {
        "Westlands": ["Westlands CBD", "Spring Valley", "Runda", "Gigiri", "Rosslyn", "Nyari", "Loresho", "Lower Kabete", "Kitisuru", "Parklands", "Highridge", "Brookside", "General Mathenge", "Rhapta Road", "Peponi Road", "Waiyaki Way", "Muthaiga", "Redhill", "Two Rivers", "UN Avenue"],
        "Dagoretti North": ["Kilimani", "Kileleshwa", "Hurlingham", "Yaya Centre", "Adams Arcade", "Kawangware", "Gatina", "Junction Mall", "Lavington", "Valley Arcade", "Kabiro", "Jamhuri Estate", "Wood Avenue", "Dennis Pritt Road"],
        "Dagoretti South": ["Riruta", "Waithaka", "Uthiru", "Ruthimitu", "Ngando", "Mutu-ini", "Dagoretti Corner", "Wangige Road", "Kikuyu Road", "Thogoto"],
        "Lang'ata": ["Karen", "Hardy", "Langata", "Lang'ata Road", "South C", "Nairobi West", "Madaraka", "Nyayo Highrise", "Mugumo-ini", "Galleria", "Bomas of Kenya", "Otiende", "T-Mall", "Wilson Airport area"],
        "Kibra": ["Laini Saba", "Lindi", "Makina", "Sarang'ombe", "Woodley", "Golf Course Estate", "Jamhuri Park area"],
        "Roysambu": ["Kahawa West", "Kahawa Sukari", "Kahawa Wendani", "Githurai 44", "Githurai 45", "Zimmerman", "Roysambu CBD", "Lumumba Drive", "Garden Estate", "Thome", "USIU area"],
        "Kasarani": ["Kasarani Mwiki Road", "Clay City", "Mwiki", "Njiru", "Ruai", "Kamulu", "Membley", "Garden Estate", "Thome", "Sunton", "Seasons", "Sportsview", "Roysambu", "Kasarani Seasons"],
        "Ruaraka": ["Baba Dogo", "Lucky Summer", "Utalii", "Mathare North", "Korogocho", "Roasters", "Garden City area", "Thika Road Mall area"],
        "Embakasi South": ["Imara Daima", "Kwa Njenga", "Kwa Reuben", "Kware", "Pipeline", "Mukuru Kwa Njenga", "Airlift", "Fedha Estate", "Nyayo Estate", "Mombasa Road"],
        "Embakasi North": ["Kariobangi North", "Dandora Phase 1", "Dandora Phase 2", "Dandora Phase 3", "Dandora Phase 4", "Dandora Phase 5", "Baba Dogo edge"],
        "Embakasi Central": ["Kayole", "Kayole North", "Kayole Central", "Kayole South", "Komarock", "Matopeni", "Spring Valley Estate", "Savannah", "Chokaa"],
        "Embakasi East": ["Utawala", "Mihango", "Embakasi Village", "Savannah", "Tassia", "Nyayo Estate", "Greenpark", "Eastern Bypass", "Airview Estate"],
        "Embakasi West": ["Umoja 1", "Umoja 2", "Mowlem", "Kariobangi South", "Buruburu", "Donholm", "Tena", "Mama Lucy area"],
        "Makadara": ["Buruburu Phase 1", "Buruburu Phase 2", "Buruburu Phase 3", "Buruburu Phase 4", "Buruburu Phase 5", "Jericho", "Maringo", "Hamza", "Makongeni", "Viwandani"],
        "Kamukunji": ["Eastleigh Section 1", "Eastleigh Section 2", "Eastleigh Section 3", "Eastleigh Section 4", "Eastleigh Section 5", "California", "Ngara", "Shauri Moyo", "Pumwani", "Majengo", "Gikomba"],
        "Starehe": ["Nairobi CBD", "Central Business District", "Pangani", "Ziwani", "Kariokor", "Landimawe", "Nairobi South", "University Way", "River Road", "Tom Mboya Street"],
        "Mathare": ["Huruma", "Mabatini", "Ngei", "Mlango Kubwa", "Kiamaiko", "Mathare North", "Mathare Area 1", "Mathare Area 4"],
    },
    "Kiambu": {
        "Gatundu North": ["Gatundu North", "Mang'u", "Githobokoni", "Chania", "Gituamba", "Kabuku", "Kiganjo", "Kairi"],
        "Gatundu South": ["Gatundu", "Kiamwangi", "Ndarugo", "Ngenda", "Kiganjo", "Kamwangi"],
        "Githunguri": ["Githunguri Town", "Komothai", "Ngewa", "Githiga", "Ikinu", "Kiairia"],
        "Juja": ["Juja Town", "Juja Farm", "Kalimoni", "Witeithie", "Theta", "Murera", "Kenyatta Road", "Juja South", "Juja North", "Mangu"],
        "Kabete": ["Kabete", "Kinoo", "Uthiru", "Wangige", "Gitaru", "Muguga", "Nyathuna", "Kanyariri", "Lower Kabete", "Kikuyu Road"],
        "Kiambaa": ["Ruaka", "Ndenderu", "Muchatha", "Karuri", "Banana Hill", "Kihara", "Cianda", "Runda Mumwe", "Two Rivers vicinity", "Ndenderu Road"],
        "Kiambu": ["Kiambu Town", "Ndumberi", "Riabai", "Ting'ang'a", "Township", "Kirigiti", "Riabai", "Kihunguro", "Kiambu Road"],
        "Kikuyu": ["Kikuyu Town", "Kinoo", "Sigona", "Karai", "Nachu", "Thogoto", "Zambezi", "Ondiri", "Gikambura", "Kamangu"],
        "Lari": ["Lari", "Kijabe", "Kinale", "Nyanduma", "Kamburu", "Lari/Kirenga", "Uplands", "Kagwe", "Kabuku"],
        "Limuru": ["Limuru Town", "Tigoni", "Ngecha", "Ndeiya", "Bibirioni", "Limuru East", "Redhill", "Rironi", "Brackenhurst", "Banana Hill edge"],
        "Ruiru": ["Ruiru Town", "Kimbo", "Kahawa Sukari", "Kahawa Wendani", "Membley", "Mwiki", "Mwihoko", "Kamakis", "Rainbow Resort area", "Gitothua", "Biashara", "Gatongora", "Kiuu", "Tatu City", "Eastern Bypass", "Kihunguro", "Matangi", "Gwa Kairu"],
        "Thika Town": ["Thika CBD", "Thika Town", "Makongeni", "Ngoingwa", "Ngoigwa", "Landless", "Section 9", "Blue Post", "Kamenu", "Hospital Ward", "Gatuanyaga", "Ngoliba", "Pilot", "Kiganjo", "Thika Greens"],
    },
    "Kajiado": {
        "Kajiado North": ["Ngong", "Ongata Rongai", "Kiserian", "Rimpa", "Nkoroi", "Matasia", "Kandisi", "Bulbul", "Karen Border", "Oloolua"],
        "Kajiado Central": ["Kajiado Town", "Isinya", "Kitengela edge", "Namanga Road", "Dalalekutuk"],
        "Kajiado East": ["Kitengela", "Athi River border", "Oloosirkon", "Kaputiei", "Kajiado East"],
        "Kajiado West": ["Kiserian Road", "Magadi", "Ewuaso Kedong", "Oloililai"],
        "Kajiado South": ["Loitokitok", "Kimana", "Rombo", "Amboseli", "Entonet"],
    },
    "Machakos": {
        "Mavoko": ["Athi River", "Mlolongo", "Syokimau", "Katani", "Sabaki", "Greatwall", "Daystar area", "Kinanie", "Kyumvi", "Lukenya"],
        "Machakos Town": ["Machakos CBD", "Mua Hills", "Kangundo Road", "Mumbuni", "Miwani", "Mutituni"],
        "Yatta": ["Kithimani", "Kangundo Road", "Yatta", "Matuu"],
        "Masinga": ["Masinga", "Kivaa", "Masinga Dam"],
        "Matungulu": ["Tala", "Matungulu", "Joska", "Kamulu", "Malaa", "Koma"],
        "Kangundo": ["Kangundo Town", "Kangundo Road", "Tala"],
        "Kathiani": ["Kathiani Town", "Mitaboni"],
        "Mwala": ["Masii", "Mwala", "Kibauni"],
    },
    "Mombasa": {
        "Nyali": ["Nyali", "Kongowea", "Mkomani", "Old Nyali", "Links Road", "Nyali Bridge", "English Point"],
        "Kisauni": ["Bamburi", "Shanzu", "Mtwapa", "Mtopanga", "Mwakirunge", "Mshomoroni"],
        "Mvita": ["Mombasa CBD", "Tudor", "Tononoka", "Old Town", "Ganjoni", "Makadara", "Majengo"],
        "Likoni": ["Likoni", "Shelly Beach", "Mtongwe", "Shika Adabu", "Diani ferry approach"],
        "Changamwe": ["Changamwe", "Chaani", "Port Reitz", "Miritini", "Magongo"],
        "Jomvu": ["Jomvu Kuu", "Mikindani", "Miritini", "Magongo"],
    },
    "Nakuru": {
        "Nakuru Town East": ["Nakuru CBD", "Section 58", "Milimani", "Naka", "Lanet", "Kivumbini", "Flamingo", "Free Area", "Pipeline", "Shabab"],
        "Nakuru Town West": ["London Estate", "Kiamunyi", "Ngata", "Barut", "Kaptembwo", "Rhonda", "Racecourse"],
        "Naivasha": ["Naivasha Town", "Karagita", "Kongoni", "Mai Mahiu", "Longonot", "Lake Naivasha"],
        "Gilgil": ["Gilgil Town", "Elementaita", "Kikopey"],
        "Njoro": ["Njoro Town", "Egerton", "Lare", "Mau Narok"],
        "Rongai": ["Rongai Town", "Menengai", "Solai"],
        "Bahati": ["Bahati", "Dundori", "Kabatini"],
    },
    "Murang'a": {
        "Kiharu": ["Murang'a Town", "Kangema Road", "Mumbi", "Township", "Kahuro"],
        "Kandara": ["Kandara", "Kagundu-ini", "Muruka"],
        "Gatanga": ["Kenol", "Sabasaba", "Gatanga", "Kariara"],
        "Maragwa": ["Maragua", "Makuyu", "Nginda", "Kambiti"],
        "Kangema": ["Kangema Town", "Kanyenya-ini"],
        "Mathioya": ["Kiriaini", "Gitugi"],
        "Kigumo": ["Kigumo", "Kinyona", "Kahumbu"],
    },
    "Nyeri": {"Nyeri Town": ["Nyeri CBD", "King'ong'o", "Ruring'u", "Skuta", "Kamakwa", "Nyaribo", "Mweiga Road"]},
    "Uasin Gishu": {"Ainabkoi": ["Eldoret CBD", "Pioneer", "Kapsoya", "Elgon View", "Kimumu", "Langas", "Annex", "Kipkaren", "Chepkoilel"]},
    "Kisumu": {"Kisumu Central": ["Kisumu CBD", "Milimani", "Mamboleo", "Migosi", "Lolwe", "Nyalenda", "Manyatta", "Kondele", "Kibos", "Riat Hills"]},
    "Kilifi": {"Kilifi North": ["Kilifi Town", "Mtwapa", "Shanzu", "Watamu", "Vipingo", "Mnarani", "Tezo"]},
    "Kwale": {"Msambweni": ["Diani", "Ukunda", "Galu", "Tiwi", "Msambweni", "Kinondo"]},
    "Laikipia": {"Laikipia East": ["Nanyuki", "Timau", "Rumuruti", "Nanyuki Town", "Thingithu", "Sweetwaters"]},
    "Trans Nzoia": {"Saboti": ["Kitale CBD", "Milimani", "Matisi", "Kiminini", "Sikhendu"]},
    "Kakamega": {"Lurambi": ["Kakamega CBD", "Milimani", "Amalemba", "Shinyalu Road", "Mumias", "Khayega"]},
    "Siaya": {"Alego Usonga": ["Siaya Town", "Ugunja", "Bondo", "Yala", "Ukwala"]},
    "Embu": {"Manyatta": ["Embu Town", "Blue Valley", "Kangaru", "Dallas", "Runyenjes"]},
}


# Wider place-name coverage for all counties. These are searchable market-area
# aliases, not claims that a neighbourhood is itself an electoral ward.
# Every county and all 290 constituencies remain represented even where a
# small locality still needs the owner/customer to type its exact estate.
EXTRA_FINE_AREAS = {
    "Kilifi": {
        "Kilifi North": ["Kilifi Town", "Mtwapa", "Shanzu", "Watamu", "Vipingo", "Mnarani", "Tezo", "Matsangoni", "Kikambala", "Kuruwitu"],
        "Kilifi South": ["Mariakani", "Mavueni", "Kaloleni Road", "Mtwapa South", "Mtepeni", "Chasimba"],
        "Kaloleni": ["Kaloleni Town", "Kayafungo", "Mwanamwinga", "Mikahani", "Mazeras"],
        "Rabai": ["Rabai", "Ribe", "Kambe", "Mwawesa", "Mazeras", "Kaliang'ombe"],
        "Ganze": ["Ganze Town", "Bamba", "Jaribuni", "Sokoke", "Matsangoni hinterland"],
        "Malindi": ["Malindi Town", "Shela", "Casuarina", "Silversands", "Mayungu", "Mambrui", "Ganda", "Kijiwetanga", "Barani"],
        "Magarini": ["Marereni", "Gongoni", "Adu", "Mambrui North", "Magarini Centre", "Bungale", "Ngomeni"],
    },
    "Makueni": {
        "Mbooni": ["Mbooni", "Kalawa", "Kisau", "Kilungu edge"],
        "Kilome": ["Kilome", "Kasikeu", "Mukaa", "Kilungu"],
        "Kaiti": ["Wote", "Ukia", "Kee", "Kilungu"],
        "Makueni": ["Wote Town", "Wote CBD", "Kathonzweni", "Muvau", "Mavindini", "Mbitini", "Kitise"],
        "Kibwezi West": ["Makindu", "Emali", "Kibwezi", "Mtito Andei", "Nguumo", "Masongaleni"],
        "Kibwezi East": ["Kibwezi East", "Kambu", "Nguu/Masumba", "Thange", "Ivingoni/Nzambani"],
    },
    "Baringo": {
        "Baringo Central": ["Kabarnet", "Tenges", "Sacho", "Ewalel Chapchap", "Kiboino", "Kapropita"],
        "Baringo North": ["Kabartonjo", "Barwessa", "Saimo", "Bartabwa"],
        "Baringo South": ["Marigat", "Mochongoi", "Mukutani", "Kisanana"],
        "Mogotio": ["Mogotio Town", "Emining", "Kisanana"],
        "Eldama Ravine": ["Eldama Ravine Town", "Mumberes", "Maji Mazuri", "Koibatek"],
        "Tiaty": ["Chemolingot", "Tangulbei", "Loiyamorok", "Churo", "Silale"],
    },
    "Bomet": {
        "Bomet Central": ["Bomet Town", "Silibwet", "Ndaraweta", "Singorwet", "Mutarakwa"],
        "Bomet East": ["Longisa", "Merigi", "Kembu", "Chemaner"],
        "Chepalungu": ["Sigor", "Kongasis", "Siongiroi", "Chebunyo"],
        "Konoin": ["Litein", "Mogogosiek", "Boito", "Kapkatet"],
        "Sotik": ["Sotik Town", "Ndanai", "Chemagel", "Kipsonoi"],
    },
    "Bungoma": {
        "Kanduyi": ["Bungoma Town", "Kanduyi", "Musikoma", "Sang'alo", "Nzoia", "Township"],
        "Webuye East": ["Webuye", "Mihuu", "Maraka"],
        "Webuye West": ["Misikhu", "Bokoli", "Matulo"],
        "Kimilili": ["Kimilili Town", "Kibingei", "Kamukuywa"],
        "Kabuchai": ["Chwele", "Mukuyuni", "Kabuchai"],
        "Bumula": ["Bumula", "Khasoko", "Kimaeti"],
        "Tongaren": ["Tongaren", "Ndalu", "Milima", "Naitiri"],
        "Mt Elgon": ["Kapsokwony", "Cheptais", "Kapkateny", "Kiboroa"],
        "Sirisia": ["Sirisia", "Lwandanyi", "Malakisi"],
        "Webuye West": ["Webuye", "Bokoli", "Misikhu"],
    },
    "Busia": {
        "Matayos": ["Matayos", "Busia Town", "Amukura Road", "Burumba"],
        "Teso North": ["Malaba", "Amagoro", "Angurai", "Malaba Township"],
        "Teso South": ["Amukura", "Angorom", "Chakol", "Amukura Centre"],
        "Nambale": ["Nambale Town", "Bumala", "Lwanya"],
        "Butula": ["Butula Town", "Bumala", "Marachi"],
        "Funyula": ["Funyula", "Bunyala", "Port Victoria", "Budimo"],
        "Budalangi": ["Bunyala", "Port Victoria", "Budalangi", "Sio Port"],
    },
    "Elgeyo-Marakwet": {
        "Keiyo South": ["Iten", "Tambach", "Chepkorio", "Kessup"],
        "Keiyo North": ["Kamariny", "Kapchemutwa", "Chepkorio"],
        "Marakwet East": ["Tot", "Chepsirei", "Endo", "Sambirir"],
        "Marakwet West": ["Kapsowar", "Kapcherop", "Arror", "Chebiemit"],
    },
    "Embu": {
        "Manyatta": ["Embu Town", "Kangaru", "Dallas", "Blue Valley", "Kianjokoma"],
        "Runyenjes": ["Runyenjes Town", "Kagaari", "Kavutiri", "Kianjokoma"],
        "Mbeere North": ["Siakago", "Ishiara", "Kiritiri", "Muminji"],
        "Mbeere South": ["Kiritiri", "Makima", "Mavuria", "Gachoka"],
    },
    "Garissa": {
        "Garissa Township": ["Garissa Town", "Bulla Iftin", "Bulla Punda", "Bulla Sheikh"],
        "Balambala": ["Balambala", "Danyere", "Sankuri"],
        "Lagdera": ["Modogashe", "Benane", "Goreale"],
        "Dadaab": ["Dadaab", "Hagadera", "Ifo", "Liboi"],
        "Fafi": ["Bura East", "Bura West", "Jarajila"],
        "Ijara": ["Masalani", "Ijara", "Hulugho"],
    },
    "Homa Bay": {
        "Homa Bay Town": ["Homa Bay Town", "Rodi Kopany", "Asego", "Arujo"],
        "Karachuonyo": ["Kendu Bay", "Kendu", "Rangwe Road"],
        "Rangwe": ["Rangwe", "Wang'chieng", "Kochia"],
        "Ndhiwa": ["Ndhiwa Town", "Pala", "Kanyamwa", "Riana"],
        "Mbita": ["Mbita", "Rusinga Island", "Kasgunga", "Lwanda"],
        "Suba South": ["Sindo", "Magunga", "Kisegi", "Gwassi"],
        "Kasipul": ["Oyugis", "Kosele", "Kendu Bay Road"],
        "Kabondo Kasipul": ["Kabondo", "Kokwanyo", "Kipasi"],
    },
    "Isiolo": {
        "Isiolo North": ["Isiolo Town", "Oldonyiro", "Ngare Mara", "Burat"],
        "Isiolo South": ["Garbatulla", "Kinna", "Merti", "Sericho"],
    },
    "Kakamega": {
        "Lugari": ["Lumakanda", "Mautuma", "Lugari", "Chekalini"],
        "Likuyani": ["Seregeya", "Matunda", "Likuyani", "Nzoia"],
        "Malava": ["Malava Town", "Manda-Shivanga", "Butali"],
        "Navakholo": ["Navakholo", "Bunyala", "Ingotse"],
        "Mumias West": ["Mumias Town", "Shianda", "Buchinga"],
        "Mumias East": ["Lusheya", "Musanda", "Etenje"],
        "Matungu": ["Koyonzo", "Kholera", "Khalaba"],
        "Butere": ["Butere Town", "Marama", "Marenyo"],
        "Khwisero": ["Khwisero", "Kisa North", "Kisa Central"],
        "Shinyalu": ["Shinyalu", "Murhanda", "Isukha"],
        "Ikolomani": ["Ikolomani", "Idakho", "Shikunga"],
    },
    "Kericho": {
        "Ainamoi": ["Kericho Town", "Kapsuser", "Kapsoit", "Kipchebor"],
        "Kipkelion East": ["Londiani", "Kedowa", "Tendeno"],
        "Kipkelion West": ["Kipkelion", "Chilchila", "Kunyak"],
        "Belgut": ["Sosiot", "Kabianga", "Waldai"],
        "Bureti": ["Litein", "Kapkatet", "Cheborge", "Kisiara"],
        "Sigowet-Soin": ["Sigowet", "Soin", "Fort Ternan"],
    },
    "Kirinyaga": {
        "Kirinyaga Central": ["Kerugoya", "Kutus", "Kagio", "Kimunye"],
        "Mwea": ["Wang'uru", "Wanguru", "Tebere", "Kimbimbi"],
        "Gichugu": ["Kianyaga", "Baricho", "Kangai"],
        "Ndia": ["Baricho", "Kagio", "Kiine"],
    },
    "Kisii": {
        "Kitutu Chache South": ["Kisii Town", "Nyanchwa", "Nyamataro", "Suneka Road"],
        "Kitutu Chache North": ["Kisii Town", "Kegogi", "Keumbu"],
        "Nyaribari Chache": ["Kisii CBD", "Jogoo", "Daraja Mbili"],
        "Nyaribari Masaba": ["Masimba", "Ichuni", "Keumbu"],
        "Bobasi": ["Ogembo", "Nyamache", "Boochi"],
        "Bomachoge Borabu": ["Etago", "Nyamarambe", "Bombaba"],
        "Bomachoge Chache": ["Suneka", "Marani", "Nyamware"],
        "South Mugirango": ["Tabaka", "Nyamarambe", "Etago"],
        "Bonchari": ["Suneka", "Riana", "Bomariba"],
    },
    "Kisumu": {
        "Kisumu East": ["Kondele", "Manyatta", "Nyalenda", "Kibos"],
        "Kisumu West": ["Maseno", "Otonglo", "Kisian", "Ojola"],
        "Seme": ["Kombewa", "Kadongo", "West Seme"],
        "Nyando": ["Ahero", "Awasi", "Pap Onditi", "Koru"],
        "Muhoroni": ["Muhoroni Town", "Chemelil", "Miwani", "Kibigori"],
        "Nyakach": ["Katito", "Pap Onditi", "Sondu", "Nyakach"],
    },
    "Kitui": {
        "Kitui Central": ["Kitui Town", "Kyangwithya", "Kwa Vonza", "Kisasi"],
        "Kitui Rural": ["Kisasi", "Mutonguni", "Mbitini"],
        "Kitui West": ["Kabati", "Mutonguni", "Matinyani"],
        "Kitui East": ["Zombe", "Mutito", "Chuluni"],
        "Kitui South": ["Ikutha", "Mutomo", "Kanziko"],
        "Mwingi Central": ["Mwingi Town", "Nguni", "Waita"],
        "Mwingi West": ["Migwani", "Kyome", "Nzeluni"],
        "Mwingi North": ["Kyuso", "Tseikuru", "Ngomeni"],
    },
    "Kwale": {
        "Matuga": ["Kwale Town", "Shimba Hills", "Mkongani", "Tiwi"],
        "Kinango": ["Kinango Town", "Mackinnon Road", "Lunga Lunga Road"],
        "Lungalunga": ["Lunga Lunga", "Vanga", "Pongwe"],
        "Msambweni": ["Diani", "Ukunda", "Galu", "Msambweni", "Kinondo", "Tiwi"],
    },
    "Laikipia": {
        "Laikipia West": ["Rumuruti", "Kinamba", "Sipili", "Ol Moran"],
        "Laikipia North": ["Doldol", "Ngarua", "Mukogodo", "Il Polei"],
        "Laikipia East": ["Nanyuki", "Timau", "Sweetwaters", "Thingithu", "Nanyuki Town"],
    },
    "Lamu": {
        "Lamu East": ["Faza", "Kiunga", "Kizingitini", "Pate Island"],
        "Lamu West": ["Lamu Old Town", "Mokowe", "Mpeketoni", "Hindi", "Witu"],
    },
    "Mandera": {
        "Mandera East": ["Mandera Town", "Arabia", "Khalalio"],
        "Mandera West": ["Takaba", "Dandu", "Gither"],
        "Mandera North": ["Rhamu", "Ashabito", "Guticha"],
        "Mandera South": ["Elwak", "Shimbir Fatuma", "Kutulo"],
        "Banissa": ["Banissa", "Malkamari"],
        "Lafey": ["Lafey", "Fino", "Sala"],
    },
    "Marsabit": {
        "Saku": ["Marsabit Town", "Marsabit CBD", "Jirime"],
        "Moyale": ["Moyale Town", "Sololo", "Uran"],
        "Laisamis": ["Laisamis", "Loiyangalani", "Kargi"],
        "North Horr": ["North Horr", "Maikona", "Turbi", "Kalacha"],
    },
    "Meru": {
        "North Imenti": ["Meru Town", "Makutano", "Kaaga", "Kanyakine Road"],
        "Central Imenti": ["Nkubu", "Kanyakine", "Mitunguu"],
        "South Imenti": ["Nkubu", "Mikumbune", "Mitunguu"],
        "Igembe Central": ["Maua", "Kianjai", "Mutuati"],
        "Igembe North": ["Laare", "Antubetwe Kiongo", "Akachiu"],
        "Igembe South": ["Maua", "Athiru Gaiti", "Amwathi"],
        "Tigania West": ["Mikinduri", "Mbeu", "Kianjai"],
        "Tigania East": ["Muthara", "Miathene", "Karama"],
        "Buuri": ["Timau", "Ruiri", "Kiirua", "Naari"],
    },
    "Migori": {
        "Suna East": ["Migori Town", "Migori CBD", "Oruba"],
        "Suna West": ["Migori Town", "Wasweta", "Bukira"],
        "Rongo": ["Rongo Town", "Awendo Road", "Kanyamkago"],
        "Awendo": ["Awendo Town", "Dede", "South Sakwa"],
        "Uriri": ["Uriri", "Oyani", "Kanyamkago"],
        "Nyatike": ["Macalder", "Muhuru Bay", "Sori", "Nyatike"],
        "Kuria West": ["Kehancha", "Isebania", "Masaba"],
        "Kuria East": ["Kegonga", "Ntimaru", "Kuria"],
    },
    "Mombasa": {
        "Nyali": ["Nyali", "Mkomani", "Old Nyali", "Links Road", "Kongowea", "English Point"],
        "Kisauni": ["Bamburi", "Shanzu", "Mtopanga", "Mshomoroni", "Mwakirunge"],
        "Mvita": ["Mombasa CBD", "Tudor", "Tononoka", "Old Town", "Ganjoni", "Kizingo", "Makupa"],
        "Likoni": ["Likoni", "Mtongwe", "Shika Adabu", "Shelly Beach"],
        "Changamwe": ["Changamwe", "Chaani", "Port Reitz", "Magongo"],
        "Jomvu": ["Jomvu Kuu", "Mikindani", "Miritini", "Magongo"],
    },
    "Murang'a": {
        "Kiharu": ["Murang'a Town", "Mumbi", "Township", "Kahuro"],
        "Kandara": ["Kandara", "Muruka", "Kagundu-ini"],
        "Gatanga": ["Kenol", "Sabasaba", "Gatanga", "Kariara"],
        "Maragwa": ["Maragua", "Makuyu", "Nginda", "Kambiti"],
        "Kigumo": ["Kigumo", "Kinyona", "Kahumbu"],
        "Kangema": ["Kangema Town", "Kanyenya-ini"],
        "Mathioya": ["Kiriaini", "Gitugi", "Kamacharia"],
    },
    "Nakuru": {
        "Naivasha": ["Naivasha Town", "Karagita", "Kongoni", "Mai Mahiu", "Longonot", "Lake Naivasha", "Kihoto"],
        "Gilgil": ["Gilgil Town", "Elementaita", "Kikopey", "Mbaruk"],
        "Nakuru Town East": ["Nakuru CBD", "Section 58", "Milimani", "Naka", "Lanet", "Kivumbini", "Flamingo", "Free Area", "Pipeline", "Shabab"],
        "Nakuru Town West": ["London Estate", "Kiamunyi", "Ngata", "Barut", "Kaptembwo", "Rhonda", "Racecourse"],
        "Molo": ["Molo Town", "Elburgon", "Turi", "Sachangwan"],
        "Kuresoi North": ["Mau Narok", "Sirikwa", "Kiptororo"],
        "Kuresoi South": ["Tinet", "Olenguruone", "Keringet"],
        "Subukia": ["Subukia Town", "Waseges", "Kabazi"],
        "Rongai": ["Rongai Town", "Menengai", "Solai", "Soin"],
        "Bahati": ["Bahati", "Dundori", "Kabatini"],
        "Njoro": ["Njoro Town", "Egerton", "Lare", "Mau Narok", "Nessuit"],
    },
    "Nandi": {
        "Emgwen": ["Kapsabet Town", "Kapsabet CBD", "Chepkumia"],
        "Nandi Hills": ["Nandi Hills Town", "Lessos", "Kapchorua"],
        "Mosop": ["Kabiyet", "Chepterwai", "Kurgung", "Kobujoi"],
        "Chesumei": ["Mosoriot", "Kaptel", "Kosirai"],
        "Aldai": ["Kobujoi", "Kaptumo", "Kabwareng"],
        "Tinderet": ["Songhor", "Kilibwoni", "Tindiret"],
    },
    "Narok": {
        "Narok North": ["Narok Town", "Narok CBD", "Ntulele"],
        "Narok East": ["Suswa", "Nairagie Enkare"],
        "Narok South": ["Ololulunga", "Mulot", "Sekenani", "Talek", "Maasai Mara"],
        "Narok West": ["Kilgoris", "Lolgorian", "Angata Barikoi"],
        "Kilgoris": ["Kilgoris Town", "Oloolunga", "Mogondo"],
        "Emurua Dikirr": ["Emurua Dikirr", "Dikirr", "Mogondo"],
    },
    "Nyamira": {
        "West Mugirango": ["Nyamira Town", "Nyansiongo", "Nyamaiya"],
        "North Mugirango": ["Ekerenyo", "Magombo", "Itibo"],
        "Kitutu Masaba": ["Keroka", "Rigoma", "Kemera"],
        "Borabu": ["Mekenene", "Nyansiongo", "Gesima"],
    },
    "Nyandarua": {
        "Ol Kalou": ["Ol Kalou Town", "Kaimbaga", "Gathanji"],
        "Kinangop": ["Engineer", "Njabini", "Magumu", "North Kinangop"],
        "Kipipiri": ["Engineer", "Wanjohi", "Geta"],
        "Ol Jorok": ["Ndaragwa Road", "Gatimu", "Ol Jorok"],
        "Ndaragwa": ["Ndaragwa", "Kiriita", "Shamata"],
    },
    "Nyeri": {
        "Nyeri Town": ["Nyeri CBD", "King'ong'o", "Ruring'u", "Skuta", "Kamakwa", "Nyaribo"],
        "Mathira": ["Karatina", "Kirimukuyu", "Kangema Road"],
        "Tetu": ["Wamagana", "Mukurwe-ini Road", "Dedan Kimathi area"],
        "Kieni": ["Mweiga", "Naromoru", "Chaka", "Naro Moru"],
        "Othaya": ["Othaya Town", "Chinga", "Iria-ini"],
        "Mukurweini": ["Mukurweini Town", "Gikondi", "Rugi"],
    },
    "Samburu": {
        "Samburu West": ["Maralal", "Maralal Town", "Suguta Marmar"],
        "Samburu North": ["Baragoi", "South Horr", "Tuum"],
        "Samburu East": ["Wamba", "Archer's Post", "Archers Post", "Kisima"],
    },
    "Siaya": {
        "Alego Usonga": ["Siaya Town", "Siaya CBD", "Akala"],
        "Ugenya": ["Ukwala", "Segero", "Sega"],
        "Ugunja": ["Ugunja Town", "Sega", "Lwandanyi"],
        "Gem": ["Yala", "Wagai", "Nyandiwa"],
        "Bondo": ["Bondo Town", "Usenge", "Bar-Kowino"],
        "Rarieda": ["Madiany", "Asembo Bay", "Aram"],
    },
    "Taita-Taveta": {
        "Voi": ["Voi Town", "Voi CBD", "Maungu", "Sagalla"],
        "Wundanyi": ["Wundanyi Town", "Mwanda", "Mbololo"],
        "Mwatate": ["Mwatate Town", "Maktau", "Bura"],
        "Taveta": ["Taveta Town", "Njukini", "Mahoo", "Taveta border"],
    },
    "Tana River": {
        "Galole": ["Hola Town", "Hola", "Wenje", "Madogo"],
        "Garsen": ["Garsen Town", "Kipini", "Ngao", "Tarasaa"],
        "Bura": ["Bura Town", "Bura East", "Bura West"],
    },
    "Tharaka-Nithi": {
        "Maara": ["Chogoria", "Marimanti Road", "Mitheru"],
        "Chuka/Igambang'ombe": ["Chuka Town", "Chuka CBD", "Kathwana", "Kaanwa"],
        "Tharaka": ["Marimanti", "Chiakariga", "Gatunga"],
    },
    "Trans Nzoia": {
        "Saboti": ["Kitale Town", "Kitale CBD", "Matisi", "Milimani"],
        "Kiminini": ["Kiminini Town", "Matunda", "Waitaluk"],
        "Endebess": ["Endebess", "Suam", "Sikhendu"],
        "Kwanza": ["Kwanza Town", "Kapomboi", "Bidii"],
        "Cherangany": ["Mwatate", "Sikhendu", "Sitatunga"],
    },
    "Turkana": {
        "Turkana Central": ["Lodwar Town", "Lodwar CBD", "Kanamkemer"],
        "Turkana North": ["Lokitaung", "Kaikor", "Lapur"],
        "Turkana West": ["Kakuma", "Lokichoggio", "Letea"],
        "Loima": ["Lorugum", "Turkwel", "Loima"],
        "Turkana South": ["Lokichar", "Kainuk", "Kapedo"],
        "Turkana East": ["Lokori", "Kalokol", "Kerio"],
    },
    "Uasin Gishu": {
        "Ainabkoi": ["Eldoret CBD", "Pioneer", "Kapsoya", "Elgon View", "Kimumu", "Annex"],
        "Kapseret": ["Langas", "Chepkoilel", "Maili Nne", "Kipkaren"],
        "Moiben": ["Moiben Town", "Kimumu", "Kaptagat Road"],
        "Soy": ["Soy Town", "Ziwa", "Kipsomba"],
        "Turbo": ["Turbo Town", "Ngeria", "Leseru"],
        "Kesses": ["Kesses", "Cheptiret", "University of Eldoret area"],
    },
    "Vihiga": {
        "Vihiga": ["Mbale Town", "Mbale CBD", "Chavakali"],
        "Sabatia": ["Chavakali", "Wodanga", "Busali"],
        "Hamisi": ["Kilingili", "Shamakhokho", "Serem"],
        "Luanda": ["Luanda Town", "Emabungo", "Ekwanda"],
        "Emuhaya": ["Ebusiralo", "Kima", "Esibuye"],
    },
    "Wajir": {
        "Wajir East": ["Wajir Town", "Wajir CBD", "Barwaqo"],
        "Wajir West": ["Griftu", "Bute", "Hadado"],
        "Wajir North": ["Buna", "Gurar", "Korondille"],
        "Wajir South": ["Habaswein", "Diff", "Dadaja Bulla"],
        "Eldas": ["Eldas Town", "Tula Tula"],
        "Tarbaj": ["Tarbaj Town", "Wagalla"],
    },
    "West Pokot": {
        "Kapenguria": ["Kapenguria Town", "Makutano", "Mnagei"],
        "Sigor": ["Sigor Town", "Ortum", "Wei Wei"],
        "Kacheliba": ["Kacheliba", "Alale", "Kiwawa"],
        "Pokot South": ["Chepareria", "Lelan", "Batei"],
    },
}

# Add and merge the additional locality seeds. Existing hand-curated areas are
# retained; repeated names are deduplicated when selector and URL data are built.
for _county, _constituencies in EXTRA_FINE_AREAS.items():
    _target = FINE_AREAS.setdefault(_county, {})
    for _constituency, _names in _constituencies.items():
        _existing = _target.setdefault(_constituency, [])
        _existing.extend(name for name in _names if name not in _existing)

# The Mtwapa market is in Kilifi County, not Mombasa County. Keep search aliases
# in the more accurate county so generated links don't misstate the location.
if "Mombasa" in FINE_AREAS and "Kisauni" in FINE_AREAS["Mombasa"]:
    FINE_AREAS["Mombasa"]["Kisauni"] = [name for name in FINE_AREAS["Mombasa"]["Kisauni"] if name.casefold() != "mtwapa"]

COUNTY_SUMMARIES = {
    "Nairobi": "Explore homes, apartments, commercial spaces and plots by Nairobi constituency, ward and neighbourhood. Search finer names such as Runda, Gigiri, Rosslyn, Nyari, Kitisuru, Kilimani, South C, Kayole and Utawala rather than relying on one city-wide search.",
    "Kiambu": "Explore Kiambu property by constituency, ward and neighbourhood, from Ruaka and Banana Hill to Ruiru, Kimbo, Kahawa Sukari, Juja, Kiambu Town, Limuru, Kikuyu, Thika and smaller local centres.",
    "Kajiado": "Explore property around Ngong, Ongata Rongai, Kiserian, Kitengela, Isinya and other Kajiado locations, selecting the closest constituency or neighbourhood where known.",
    "Machakos": "Explore homes, plots and commercial premises in Machakos County, including the Mavoko corridor around Athi River, Mlolongo, Syokimau and Katani, as well as Machakos Town and surrounding centres.",
    "Mombasa": "Explore coastal homes, stays, shops and property across Mombasa's constituencies and popular locations including Nyali, Bamburi, Shanzu, Tudor, Likoni, Changamwe and Miritini.",
    "Nakuru": "Explore rental homes, houses for sale, land and business spaces across Nakuru County, including Nakuru Town, Naivasha, Gilgil, Lanet, Milimani, Naka, London Estate and surrounding communities.",
}


def slugify(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("&", " and ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def county_by_slug(value):
    wanted = slugify(value)
    return next((name for name in COUNTY_CONSTITUENCIES if slugify(name) == wanted), None)


def constituency_by_slug(county, value):
    wanted = slugify(value)
    return next((name for name in COUNTY_CONSTITUENCIES.get(county, []) if slugify(name) == wanted), None)


def ward_map(county):
    if county == "Nairobi":
        return NAIROBI_WARDS
    if county == "Kiambu":
        return KIAMBU_WARDS
    return {}


def county_fine_areas(county):
    rows = []
    for constituency, names in FINE_AREAS.get(county, {}).items():
        for name in names:
            if not any(row["slug"] == slugify(name) for row in rows):
                rows.append({"name": name, "slug": slugify(name), "constituency": constituency})
    return rows


def all_known_localities(county):
    values = set(COUNTY_CONSTITUENCIES.get(county, []))
    for key, names in ward_map(county).items():
        values.add(key)
        values.update(names)
    for names in FINE_AREAS.get(county, {}).values():
        values.update(names)
    values.add(county)
    return sorted(values)


def selector_data():
    """Small JSON-ready hierarchy for the owner listing form."""
    data = {}
    for county, constituencies in COUNTY_CONSTITUENCIES.items():
        children = {}
        wards = ward_map(county)
        fine = FINE_AREAS.get(county, {})
        for constituency in constituencies:
            localities = list(wards.get(constituency, []))
            localities.extend(fine.get(constituency, []))
            if not localities:
                # A constituency is always a usable fallback; the form also keeps
                # a separate free-text estate/road field so no community is blocked.
                localities = [constituency]
            children[constituency] = sorted(dict.fromkeys(localities), key=str.casefold)
        data[county] = children
    return data
