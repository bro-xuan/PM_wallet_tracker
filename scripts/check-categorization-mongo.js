// MongoDB queries to verify categorization system
// Run with: mongosh <your-db-name> check-categorization-mongo.js

print("\n" + "=".repeat(60));
print("CATEGORIZATION SYSTEM VERIFICATION");
print("=".repeat(60));

// 1. Check user configs
print("\n1. USER CONFIGS");
print("-".repeat(60));

const configs = db.whaleAlertConfigs.find({}).toArray();
print(`Total configs: ${configs.length}`);

let withSelected = 0;
let withExclude = 0;
let empty = 0;

configs.forEach(config => {
  const userId = config.userId || 'unknown';
  const selected = config.selectedCategories || [];
  const exclude = config.excludeCategories || [];
  const enabled = config.enabled || false;
  
  if (selected.length > 0) {
    withSelected++;
    print(`\n✅ User ${userId.substring(0, 8)}...`);
    print(`   selectedCategories: ${JSON.stringify(selected)}`);
    print(`   enabled: ${enabled}`);
  } else if (exclude.length > 0) {
    withExclude++;
    print(`\n⚠️  User ${userId.substring(0, 8)}... (LEGACY)`);
    print(`   excludeCategories: ${JSON.stringify(exclude)}`);
    print(`   selectedCategories: ${JSON.stringify(selected)} (empty - will be migrated)`);
  } else {
    empty++;
    print(`\n❌ User ${userId.substring(0, 8)}... (NO CATEGORIES)`);
    print(`   selectedCategories: ${JSON.stringify(selected)} (empty = all categories allowed)`);
  }
});

print(`\n📊 Summary:`);
print(`   With selectedCategories: ${withSelected}`);
print(`   With excludeCategories (legacy): ${withExclude}`);
print(`   No category filters: ${empty}`);

// 2. Check markets
print("\n\n2. MARKET CATEGORIES");
print("-".repeat(60));

const totalMarkets = db.marketMetadata.countDocuments({});
const marketsWithCategories = db.marketMetadata.countDocuments({ 
  categories: { $exists: true, $ne: [] } 
});
const marketsWithoutCategories = db.marketMetadata.countDocuments({ 
  $or: [
    { categories: { $exists: false } },
    { categories: [] }
  ]
});
const marketsWithTagIds = db.marketMetadata.countDocuments({ 
  tagIds: { $exists: true, $ne: [] } 
});

print(`Total markets: ${totalMarkets}`);
print(`Markets WITH categories: ${marketsWithCategories}`);
print(`Markets WITHOUT categories: ${marketsWithoutCategories}`);
print(`Markets with tagIds: ${marketsWithTagIds}`);

// Sample markets
print("\n📋 Sample markets:");
const sampleMarkets = db.marketMetadata.find({}).limit(5).toArray();

sampleMarkets.forEach(market => {
  const conditionId = market.conditionId || 'unknown';
  const title = (market.title || 'Unknown').substring(0, 50);
  const categories = market.categories || [];
  const tagIds = market.tagIds || [];
  
  if (categories.length > 0) {
    print(`\n✅ ${conditionId.substring(0, 16)}...`);
    print(`   Title: ${title}`);
    print(`   Categories: ${JSON.stringify(categories)}`);
  } else if (tagIds.length > 0) {
    print(`\n⚠️  ${conditionId.substring(0, 16)}... (NO CATEGORIES, but has tagIds)`);
    print(`   Title: ${title}`);
    print(`   TagIds: ${tagIds.slice(0, 3).join(', ')}... (${tagIds.length} total)`);
  } else {
    print(`\n❌ ${conditionId.substring(0, 16)}... (NO CATEGORIES, NO TAGIDS)`);
    print(`   Title: ${title}`);
  }
});

// 3. Check tag mappings
print("\n\n3. TAG CATEGORY MAPPINGS");
print("-".repeat(60));

const tagMappingsCount = db.tagCategoryMappings.countDocuments({});
print(`Total tag mappings: ${tagMappingsCount}`);

const exampleMapping = db.tagCategoryMappings.findOne({});
if (exampleMapping) {
  print(`\n📋 Example mapping:`);
  print(`   tagId: ${exampleMapping._id}`);
  print(`   label: ${exampleMapping.label || 'N/A'}`);
  print(`   categories: ${JSON.stringify(exampleMapping.categories || [])}`);
} else {
  print(`\n⚠️  No tag mappings found yet`);
}

// 4. Test filter matching
print("\n\n4. FILTER MATCHING TEST");
print("-".repeat(60));

const userWithSelected = db.whaleAlertConfigs.findOne({
  selectedCategories: { $exists: true, $ne: [] }
});

if (!userWithSelected) {
  print("⚠️  No users with selectedCategories found");
  print("   → All categories are allowed for all users");
} else {
  const selectedCategories = userWithSelected.selectedCategories || [];
  print(`Testing with user: ${userWithSelected.userId.substring(0, 8)}...`);
  print(`Selected categories: ${JSON.stringify(selectedCategories)}`);
  
  const testMarkets = db.marketMetadata.find({}).limit(3).toArray();
  print(`\n📋 Testing ${testMarkets.length} markets:`);
  
  testMarkets.forEach(market => {
    const conditionId = market.conditionId || 'unknown';
    const marketCategories = market.categories || [];
    const title = (market.title || 'Unknown').substring(0, 40);
    
    if (marketCategories.length === 0) {
      print(`\n❌ ${conditionId.substring(0, 16)}... - NO CATEGORIES`);
      print(`   Title: ${title}`);
      print(`   → Would be FILTERED OUT`);
    } else {
      const hasIntersection = selectedCategories.some(cat => marketCategories.includes(cat));
      if (hasIntersection) {
        print(`\n✅ ${conditionId.substring(0, 16)}... - MATCHES`);
        print(`   Title: ${title}`);
        print(`   Market categories: ${JSON.stringify(marketCategories)}`);
        print(`   → Would PASS filter`);
      } else {
        print(`\n🚫 ${conditionId.substring(0, 16)}... - NO MATCH`);
        print(`   Title: ${title}`);
        print(`   Market categories: ${JSON.stringify(marketCategories)}`);
        print(`   → Would be FILTERED OUT`);
      }
    }
  });
}

print("\n" + "=".repeat(60));
print("VERIFICATION COMPLETE");
print("=".repeat(60));

